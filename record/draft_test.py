#!/usr/bin/env python3
"""Score the record drafter: does it cite the right cause, and the right governing terms?

For every change order in the synthetic record, the sub's note is its Description piece. Two versions:
  plain  the note as written (it often names the RFI or ASI, e.g. "per RFI-112")
  blind  the note with document numbers removed (RFI-112, ASI-014, FR-33, dates), the harder and more realistic case
Truth comes from the record's links: caused_by (the cause document) and cites (governing contract/spec sections).
Split: CP-02xx = dev, CP-04xx = test. Retrieval (does the right cause appear among the candidates at all?) is
reported separately from the model's choice, so a miss can be traced to the right part.

    python3 record/draft_test.py --model llama3.1:8b              (writes record/results/draft_<model>.json)
    python3 record/draft_test.py --retrieval-only                 (no model)
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "record"))
import draft as dr  # noqa: E402

BLIND = re.compile(r"\b(?:RFI|ASI|FR|FO|NL|OE|OL|CP|SCH)-?\s?\d[\w.-]*|\b\d{4}-\d{2}-\d{2}\b|\bsubmittal\s+\d[\d\s-]*\d", re.I)


def truth(bundle):
    t = {}
    for l in bundle["links"]:
        if l["from"].startswith("CP-") and l["relation"] in ("caused_by", "cites"):
            x = t.setdefault(l["from"], {"cause": set(), "cites": set()})
            if l["relation"] == "caused_by":
                x["cause"].add(l["to"])
            else:
                x["cites"].add(f"{l['to']}|{l.get('to_section')}")
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=dr.MODEL)
    ap.add_argument("--retrieval-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    b = dr.load_bundle()
    T = truth(b)
    cos = [d for d in b["documents"] if d["kind"] == "change_order" and d["number"] in T]
    if a.limit:
        cos = cos[: a.limit]
    rows = []
    for d in cos:
        note = next((p["body"] for p in d["pieces"] if p.get("section") == "Description"), d["pieces"][0]["body"])
        for variant, text in (("plain", note), ("blind", BLIND.sub("", note))):
            ev, tm = dr.candidates(b, text, exclude=(d["key"],))
            cause_docs = T[d["number"]]["cause"]
            in_cands = any(e["doc"] in cause_docs for e in ev)
            row = {"id": d["number"], "split": "dev" if d["number"].startswith("CP-02") else "test", "variant": variant,
                   "retrieved": in_cands, "truth_cause": sorted(cause_docs)}
            if not a.retrieval_only:
                t0 = time.time()
                try:
                    res = dr.draft(text, b, a.model, exclude=(d["key"],))
                    got = res["cause"]["doc"] if res["cause"] else None
                    gov = {g["id"] for g in res["governing"]}
                    row.update({"cause": got, "cause_right": got in cause_docs, "governing": sorted(gov),
                                "governing_right": len(gov & T[d["number"]]["cites"]), "governing_n": len(gov),
                                "notes": res["notes"], "scope": res["draft"].get("scope"), "error": None})
                except Exception as e:  # noqa: BLE001
                    row.update({"cause": None, "cause_right": False, "error": f"{type(e).__name__}: {e}"})
                row["seconds"] = round(time.time() - t0, 1)
                print(f"{d['number']} {variant}: cause {row.get('cause')} ({'right' if row.get('cause_right') else 'wrong'}), retrieved={in_cands}", flush=True)
            rows.append(row)
    summary = {}
    for split in ("dev", "test"):
        for variant in ("plain", "blind"):
            rs = [r for r in rows if r["split"] == split and r["variant"] == variant]
            if not rs:
                continue
            s = {"of": len(rs), "cause_in_candidates": sum(r["retrieved"] for r in rs)}
            if not a.retrieval_only:
                s["cause_right"] = sum(bool(r.get("cause_right")) for r in rs)
                n = sum(r.get("governing_n", 0) for r in rs)
                s["governing_precision"] = round(sum(r.get("governing_right", 0) for r in rs) / n, 3) if n else None
                s["flagged_numbers"] = sum(any("numbers" in x for x in r.get("notes") or []) for r in rs)
            summary[f"{split}/{variant}"] = s
    print(json.dumps(summary, indent=1))
    if not a.retrieval_only:
        out = ROOT / "record" / "results" / f"draft_{a.model.replace(':', '_').replace('/', '_')}.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps({"meta": {"model": a.model, "date": time.strftime("%Y-%m-%d"), "synthetic": True}, "summary": summary, "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
