#!/usr/bin/env python3
"""Draft a formal change proposal from a sub's plain-language note, citing only real pieces of the project record.

Guardrails (same rule as the contract reader: choose from real options, prove it in code):
  - Code retrieves the candidate pieces from the record (RFIs, ASIs, submittals, daily reports, other correspondence,
    contract clauses, spec paragraphs) by word overlap with the note.
  - The model may only cite those candidates, by id (its output is constrained to them), or say "none".
  - Code checks the draft: the cause must be an event document (not a contract clause); every number in the scope
    text must appear in the note or in a cited piece (no invented quantities or dollars).
  - A person confirms the draft in the thread before it goes anywhere.

Scoring (record/draft_test.py): the right cause is the document the record links as caused_by.

    python3 record/draft.py "RFI-112 answer adds two roof drains at the gym..."
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")
MODEL = os.environ.get("LOCAL_MODEL", "llama3.1:8b")
EVENT_KINDS = {"rfi", "asi", "submittal", "daily_report", "other", "minutes"}
TERM_KINDS = {"contract", "spec"}
STOP = set("the a an and or of to in on for with by at from is are was be this that it as into per about add added adds new work "
           "we our us they their will would should can could has have had not no any all".split())


def words(s):
    return {w for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", (s or "").lower()) if len(w) > 2 and w not in STOP}


def load_bundle(path=None):
    return json.loads(Path(path or ROOT / "record" / "bundle.json").read_text())


def candidates(bundle, note, k_events=12, k_terms=8, exclude=()):
    nw = words(note)
    ev, tm = [], []
    for d in bundle["documents"]:
        if d["key"] in exclude or d["kind"] in ("change_order", "schedule"):
            continue
        for p in d["pieces"]:
            text = (d.get("number") or "") + " " + d.get("title", "") + " " + (p.get("section") or "") + " " + p["body"]
            score = len(nw & words(text))
            if d.get("number") and d["number"].lower() in (note or "").lower():
                score += 6
            if score:
                item = {"id": f"{d['key']}|{p.get('section') or p['ordinal']}", "doc": d["key"], "kind": d["kind"], "number": d.get("number"),
                        "section": p.get("section"), "date": p.get("piece_date") or d.get("issued_on"), "body": p["body"], "score": score}
                (ev if d["kind"] in EVENT_KINDS else tm if d["kind"] in TERM_KINDS else []).append(item)
    ev.sort(key=lambda x: (-x["score"], x["id"]))
    tm.sort(key=lambda x: (-x["score"], x["id"]))
    return ev[:k_events], tm[:k_terms]


SYSTEM = ("You help a general contractor turn a subcontractor's plain-language note into a formal change proposal. "
          "Choose the ONE record entry that caused the change (an RFI answer, ASI, returned submittal, daily/field report or owner letter) "
          "from the listed EVENT ids, or \"none\". Choose up to 4 CONTRACT/SPEC ids that govern pricing and notice. "
          "Write a short, formal scope description (2-3 sentences) using only facts in the note and the entries you cite. "
          "Do not invent quantities, dollars, dates or durations.")


def schema(ev, tm):
    return {"type": "object", "properties": {
        "cause": {"type": "string", "enum": [e["id"] for e in ev] + ["none"]},
        "governing": {"type": "array", "maxItems": 4, "items": {"type": "string", "enum": [t["id"] for t in tm]}},
        "scope": {"type": "string"}}, "required": ["cause", "governing", "scope"]}


def call(note, ev, tm, model=MODEL, host=HOST):
    lines = "EVENTS:\n" + "\n".join(f"{e['id']}: ({e['kind']}, {e['date'] or 'undated'}) {e['body'][:300]}" for e in ev)
    lines += "\n\nCONTRACT/SPEC:\n" + "\n".join(f"{t['id']}: {t['body'][:240]}" for t in tm)
    body = {"model": model, "stream": False, "format": schema(ev, tm), "keep_alive": "2h",
            "options": {"temperature": 0.2, "num_ctx": 8192, "num_predict": 600},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Sub's note:\n{note}\n\n{lines}"}]}
    req = urllib.request.Request(host + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(json.loads(r.read())["message"]["content"])


def numbers(s):
    return {x.replace(",", "") for x in re.findall(r"\d[\d,]*(?:\.\d+)?", s or "")}


def check(out, note, ev, tm):
    """Code's check of the model's draft. Returns notes; an empty list means nothing to flag."""
    notes = []
    byid = {x["id"]: x for x in ev + tm}
    cause = byid.get(out.get("cause"))
    if out.get("cause") == "none" or not cause:
        notes.append("No cause cited: link the RFI, ASI, submittal or report before sending.")
    cited = " ".join([note] + [byid[i]["body"] for i in [out.get("cause")] + list(out.get("governing") or []) if i in byid])
    extra = numbers(out.get("scope")) - numbers(cited)
    if extra:
        notes.append("The scope has numbers that aren't in the note or the cited entries: " + ", ".join(sorted(extra)) + ". Removed or check them.")
    return notes


def draft(note, bundle=None, model=MODEL, host=HOST, exclude=()):
    bundle = bundle or load_bundle()
    ev, tm = candidates(bundle, note, exclude=exclude)
    out = call(note, ev, tm, model, host)
    byid = {x["id"]: x for x in ev + tm}
    return {"draft": out, "notes": check(out, note, ev, tm), "cause": byid.get(out.get("cause")),
            "governing": [byid[i] for i in out.get("governing") or [] if i in byid], "candidates": len(ev) + len(tm), "model": model}


if __name__ == "__main__":
    print(json.dumps(draft(" ".join(sys.argv[1:])), indent=1))
