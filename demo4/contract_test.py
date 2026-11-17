#!/usr/bin/env python3
"""Score the contract term reader against the answer key.

Runs demo4/contract_extract.py on each synthetic contract (A: the sample, B: demo4/data/contract_b.md), compares
every term with demo4/data/contract_terms_key.json, and writes demo4/results/contract_test.json.

What is counted, per term:
  right      value matches the key
  wrong      value differs from the key
  missed     the reader said "not stated" but the key has a value
  confident_wrong   wrong AND marked "verified"  <- the dangerous one; the confirm screen would show it green
Contract A is the dev contract (prompts and keywords were tuned on it). Contract B is held out: report it separately.

    python3 demo4/contract_test.py --model llama3.1:8b --runs 3
    python3 demo4/contract_test.py --score-only      (re-score the saved readings)
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo4"))
import contract_extract as ce  # noqa: E402

FILES = {"A": ROOT / "demo1" / "data" / "synthetic_contract.md", "B": ROOT / "demo4" / "data" / "contract_b.md"}
SPLIT = {"A": "dev", "B": "test"}
OUT = ROOT / "demo4" / "results" / "contract_test.json"


def load_key():
    raw = json.loads((ROOT / "demo4" / "data" / "contract_terms_key.json").read_text())
    if isinstance(raw, list):
        raw = {c.get("id") or c.get("contract"): c for c in raw}
    out = {}
    for k, v in raw.items():
        name = "A" if k.upper().endswith("A") or "sample" in k.lower() else "B" if k.upper().endswith("B") else k
        out[name] = v.get("terms", v)
    return out


def same(a, b):
    if isinstance(b, dict):
        return isinstance(a, dict) and all(same(a.get(k), v) for k, v in b.items())
    if isinstance(b, list):
        return isinstance(a, list) and sorted(map(str, a)) == sorted(map(str, b))
    if isinstance(b, bool) or isinstance(a, bool):
        return a is b
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return a == b


def score(readings, key):
    report = {}
    for name, r in readings.items():
        terms, kt = r["terms"], key.get(name, {})
        rows, c = [], {"right": 0, "wrong": 0, "missed": 0, "confident_wrong": 0, "verified": 0, "of": 0}
        for k, want in kt.items():
            want_v = want.get("value") if isinstance(want, dict) else want
            if want_v is None:
                continue
            got = terms.get(k) or {}
            c["of"] += 1
            st = got.get("status")
            c["verified"] += st == "verified"
            if got.get("value") is None:
                res = "missed"
            elif same(got.get("value"), want_v):
                res = "right"
            else:
                res = "wrong"
                c["confident_wrong"] += st == "verified"
            c[res] += 1
            rows.append({"term": k, "result": res, "status": st, "got": got.get("value"), "want": want_v,
                         "section": got.get("section"), "want_section": want.get("section") if isinstance(want, dict) else None})
        report[name] = {"split": SPLIT.get(name, "?"), **c, "rows": rows}
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=ce.MODEL)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--score-only", action="store_true")
    a = ap.parse_args()
    key = load_key()
    if a.score_only:
        saved = json.loads(OUT.read_text())
        readings, meta = saved["readings"], saved["meta"]
    else:
        readings = {}
        for name, path in FILES.items():
            if path.exists():
                print("reading contract", name, "...", flush=True)
                readings[name] = ce.extract(path.read_text(), a.model, runs=a.runs)
                print(f"  {readings[name]['seconds']} s", flush=True)
        meta = {"model": a.model, "runs": a.runs}
    rep = score(readings, key)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"meta": meta, "score": rep, "readings": readings}, indent=1))
    for name, s in rep.items():
        print(f"contract {name} ({s['split']}): {s['right']}/{s['of']} right, {s['wrong']} wrong, {s['missed']} missed, "
              f"{s['confident_wrong']} wrong but marked verified")
        for row in s["rows"]:
            if row["result"] != "right":
                print(f"   {row['term']}: got {row['got']!r} ({row['status']}), key {row['want']!r}")


if __name__ == "__main__":
    main()
