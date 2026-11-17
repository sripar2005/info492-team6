#!/usr/bin/env python3
"""Draft a fragnet (the change's activities and their links into the schedule) from a change order's narrative.

Guardrails:
  - Code picks the schedule activities the model may see (keyword overlap with the narrative, plus the critical path),
    and the model's links are constrained to those activity ids and F-1..F-4. It cannot invent an activity id.
  - The model never computes a delay. The time impact analysis is done in code (assets/schedule.js, demo4/cpm_ref.py).
  - It drafts several times; if the drafts differ, the result says so and the person looks closer.
  - A person confirms or edits every draft before the analysis runs.

Used by serve_local.py (POST /api/fragnet). Command line:
    python3 demo4/fragnet_draft.py --case CP-0401 [--runs 3]
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")
MODEL = os.environ.get("LOCAL_MODEL", "llama3.1:8b")
MAX_NEW = 4
STOP = set("the a an and or of to in on for with by at from is are was be this that it as into per about add added adds new work".split())

SYSTEM = ("You are a construction scheduler preparing a fragnet for a time impact analysis (AACE 52R-06). "
          "From the change order narrative, list the NEW activities the change requires (at most 4), each with a duration in "
          "working days, and link each one into the existing schedule: what it must start after, and what cannot start until it "
          "finishes. Use only the activity ids listed. Name new activities F-1, F-2, ... in order. Use FS links unless the narrative "
          "clearly says work overlaps. Do not estimate the project delay; code computes it.")


def words(s):
    return {w for w in re.findall(r"[a-z]+", (s or "").lower()) if len(w) > 2 and w not in STOP}


def pick_activities(activities, narrative, critical=(), k=40):
    """The schedule activities the model may link to: best keyword overlap with the narrative, plus the critical path."""
    nw = words(narrative)
    scored = sorted(activities, key=lambda a: -len(nw & words(a.get("name", "") + " " + (a.get("wbs") or ""))))
    keep, seen = [], set()
    for a in scored[:k] + [a for a in activities if a["id"] in set(critical)]:
        if a["id"] not in seen:
            seen.add(a["id"])
            keep.append(a)
    order = {a["id"]: i for i, a in enumerate(activities)}
    return sorted(keep, key=lambda a: order[a["id"]])


def schema(ids):
    new = [f"F-{i}" for i in range(1, MAX_NEW + 1)]
    node = {"type": "string", "enum": list(ids) + new}
    return {"type": "object", "properties": {
        "activities": {"type": "array", "maxItems": MAX_NEW, "items": {"type": "object", "properties": {
            "id": {"type": "string", "enum": new}, "name": {"type": "string"}, "duration": {"type": "integer", "minimum": 0, "maximum": 200}},
            "required": ["id", "name", "duration"]}},
        "relationships": {"type": "array", "maxItems": 12, "items": {"type": "object", "properties": {
            "pred": node, "succ": node, "type": {"type": "string", "enum": ["FS", "SS", "FF"]}, "lag": {"type": "integer", "minimum": -10, "maximum": 30}},
            "required": ["pred", "succ", "type", "lag"]}}},
        "required": ["activities", "relationships"]}


def call(user, sch, model=MODEL, host=HOST):
    body = {"model": model, "stream": False, "format": sch, "keep_alive": "2h",
            "options": {"temperature": 0.3, "num_ctx": 8192, "num_predict": 900},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]}
    req = urllib.request.Request(host + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(json.loads(r.read())["message"]["content"])


MAX_LAG = 5
NOT_WORK = re.compile(r"general conditions|extended (?:time|overhead)|delay|time extension|impact", re.I)


def norm_words(name):
    return {w for w in re.findall(r"[a-z]+", (name or "").lower()) if w not in STOP and len(w) > 2}


def same_work(a, b):
    """Two activity names describe the same work: most of the shorter name's words are in the other."""
    wa, wb = norm_words(a), norm_words(b)
    if not wa or not wb:
        return False
    small = wa if len(wa) <= len(wb) else wb
    return len(wa & wb) / len(small) >= 0.75


def has_cycle(rels):
    g = {}
    for r in rels:
        g.setdefault(r["pred"], []).append(r["succ"])
    seen, stack = set(), set()

    def visit(n):
        if n in stack:
            return True
        if n in seen:
            return False
        seen.add(n); stack.add(n)
        hit = any(visit(m) for m in g.get(n, []))
        stack.discard(n)
        return hit
    return any(visit(n) for n in list(g))


def clean(draft, ids, activities=None, relationships=None, claimed_days=None):
    """Code's check on a draft. Drops: links to undefined ids, self-links, duplicates, links between existing
    activities, new activities that repeat existing schedule work or aren't physical work (e.g. 'extended general
    conditions'), and links that would close a loop. Caps long waits on links. Flags durations far past the claim."""
    notes, acts = [], []
    existing = {a["id"]: a.get("name", "") for a in (activities or [])}
    for a in draft.get("activities", []):
        if a["id"] in {x["id"] for x in acts}:
            continue
        name = a["name"].strip()[:80] or a["id"]
        dup = next((eid for eid, en in existing.items() if same_work(name, en)), None)
        if dup:
            notes.append(f"Dropped {a['id']} '{name}': it repeats existing activity {dup} ({existing[dup]}). A fragnet only adds the change's own work.")
            continue
        if NOT_WORK.search(name):
            notes.append(f"Dropped {a['id']} '{name}': it is a cost or a delay, not work; the analysis computes delay itself.")
            continue
        acts.append({"id": a["id"], "name": name, "duration": int(a["duration"])})
    have = set(ids) | {a["id"] for a in acts}
    rels, seen = [], set()
    base = [dict(r) for r in (relationships or [])]
    for r in draft.get("relationships", []):
        key = (r["pred"], r["succ"])
        if r["pred"] not in have or r["succ"] not in have or r["pred"] == r["succ"] or key in seen:
            if r["pred"] in have and r["succ"] in have:
                notes.append(f"Dropped link {r['pred']} -> {r['succ']}.")
            continue
        if r["pred"] in ids and r["succ"] in ids:
            notes.append(f"Dropped link {r['pred']} -> {r['succ']} between existing activities (a fragnet only adds the change's work).")
            continue
        lag = int(r.get("lag") or 0)
        if abs(lag) > MAX_LAG:
            notes.append(f"Link {r['pred']} -> {r['succ']} had a {lag}-day wait; set to 0. Waiting time should be its own activity with a reason.")
            lag = 0
        cand = {"pred": r["pred"], "succ": r["succ"], "type": r["type"], "lag": lag}
        if base and has_cycle(base + rels + [cand]):
            notes.append(f"Dropped link {r['pred']} -> {r['succ']}: it would make the schedule loop back on itself.")
            continue
        seen.add(key)
        rels.append(cand)
    for a in acts:
        if not any(r["succ"] == a["id"] for r in rels):
            notes.append(f"{a['id']} has no predecessor: it will start at the data date.")
        if not any(r["pred"] == a["id"] for r in rels):
            notes.append(f"{a['id']} has no successor: it can only delay the finish if it ends after it.")
    if claimed_days:
        total = sum(a["duration"] for a in acts)
        if total > 2 * max(1, round(claimed_days * 5 / 7)):
            notes.append(f"The new work adds up to {total} working days, far more than the {claimed_days} days claimed. Check the durations.")
    return {"activities": acts, "relationships": rels}, notes


def anchors(f, ids):
    ids = set(ids)
    return (tuple(sorted({r["pred"] for r in f["relationships"] if r["pred"] in ids})),
            tuple(sorted({r["succ"] for r in f["relationships"] if r["succ"] in ids})))


def agree(drafts, ids):
    """Drafts agree when they hang off the same existing activities and their total work is within 20%."""
    a0, t0 = anchors(drafts[0], ids), sum(a["duration"] for a in drafts[0]["activities"])
    for d in drafts[1:]:
        t = sum(a["duration"] for a in d["activities"])
        if anchors(d, ids) != a0 or abs(t - t0) > 0.2 * max(t, t0, 1):
            return False
    return True


def draft(narrative, activities, claimed_days=None, critical=(), model=MODEL, host=HOST, runs=3, relationships=None):
    shown = pick_activities(activities, narrative, critical)
    ids = [a["id"] for a in shown]
    lines = "\n".join(f"{a['id']} | {a.get('name', '')} | {a.get('duration', '')}d | {a.get('wbs') or ''}" for a in shown)
    user = f"Change order narrative:\n{narrative}\n\nExisting schedule activities (id | name | duration | WBS):\n{lines}"
    t0 = time.time()
    all_ids = [a["id"] for a in activities]
    drafts = [clean(call(user, schema(ids), model, host), all_ids, activities, relationships, claimed_days) for _ in range(max(1, runs))]
    ok = agree([d[0] for d in drafts], all_ids)
    diff = "" if ok else "they link to different activities or differ in total work by more than 20%"
    f, notes = drafts[0]
    return {"fragnet": f, "notes": notes, "agree": ok, "disagreement": diff, "drafts": [d[0] for d in drafts], "model": model,
            "seconds": round(time.time() - t0, 1), "shown_activities": len(shown)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--model", default=MODEL)
    a = ap.parse_args()
    data = ROOT / "demo4" / "data"
    case = [c for c in json.loads((data / "cases.json").read_text())["cases"] if c["id"] == a.case][0]
    sched = json.loads((data / "schedule.json").read_text())
    print(json.dumps(draft(case["time"]["narrative"], sched["activities"], case["time"].get("claimed_days"), model=a.model, runs=a.runs), indent=1))


if __name__ == "__main__":
    sys.exit(main())
