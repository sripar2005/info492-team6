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


def clean(draft, ids):
    """Drop links to new ids that weren't defined, self-links and duplicates; note what was dropped."""
    notes, acts = [], []
    for a in draft.get("activities", []):
        if a["id"] not in {x["id"] for x in acts}:
            acts.append({"id": a["id"], "name": a["name"].strip()[:80] or a["id"], "duration": int(a["duration"])})
    have = set(ids) | {a["id"] for a in acts}
    rels, seen = [], set()
    for r in draft.get("relationships", []):
        key = (r["pred"], r["succ"])
        if r["pred"] not in have or r["succ"] not in have or r["pred"] == r["succ"] or key in seen:
            notes.append(f"Dropped link {r['pred']} -> {r['succ']}.")
            continue
        if r["pred"] in ids and r["succ"] in ids:
            notes.append(f"Dropped link {r['pred']} -> {r['succ']} between existing activities (a fragnet only adds the change's work).")
            continue
        seen.add(key)
        rels.append({"pred": r["pred"], "succ": r["succ"], "type": r["type"], "lag": int(r.get("lag") or 0)})
    for a in acts:
        if not any(r["succ"] == a["id"] for r in rels):
            notes.append(f"{a['id']} has no predecessor: it will start at the data date.")
        if not any(r["pred"] == a["id"] for r in rels):
            notes.append(f"{a['id']} has no successor: it can only delay the finish if it ends after it.")
    return {"activities": acts, "relationships": rels}, notes


def signature(f):
    return (tuple(sorted((a["id"], a["duration"]) for a in f["activities"])),
            tuple(sorted((r["pred"], r["succ"], r["type"]) for r in f["relationships"])))


def draft(narrative, activities, claimed_days=None, critical=(), model=MODEL, host=HOST, runs=3):
    shown = pick_activities(activities, narrative, critical)
    ids = [a["id"] for a in shown]
    lines = "\n".join(f"{a['id']} | {a.get('name', '')} | {a.get('duration', '')}d | {a.get('wbs') or ''}" for a in shown)
    user = f"Change order narrative:\n{narrative}\n\nExisting schedule activities (id | name | duration | WBS):\n{lines}"
    t0 = time.time()
    drafts = [clean(call(user, schema(ids), model, host), ids) for _ in range(max(1, runs))]
    sigs = [signature(d[0]) for d in drafts]
    agree = all(s == sigs[0] for s in sigs)
    diff = ""
    if not agree:
        durs = {tuple(x) for x, _ in sigs}
        diff = "different activities or durations" if len(durs) > 1 else "different links"
    f, notes = drafts[0]
    return {"fragnet": f, "notes": notes, "agree": agree, "disagreement": diff, "drafts": [d[0] for d in drafts], "model": model,
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
