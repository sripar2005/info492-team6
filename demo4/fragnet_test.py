#!/usr/bin/env python3
"""Score the fragnet drafter on the Demo 4 change orders, dev and test reported separately.

For each change order with time impact: the model drafts the fragnet from the narrative (3 drafts), code runs the
time impact analysis on the draft (demo4/cpm_ref.py), and the result is compared with the answer key.
Counted per case:
  delay_exact     computed delay (calendar days) equals the key's
  delay_within_2  within 2 calendar days
  critical_same   "is the change on the critical path" agrees with the key
  links_same      the draft links into the same schedule activities as the reference fragnet (ignores F- ids)
  agreed          the 3 drafts agreed (signals reliability; disagreeing drafts get a closer look)
Saves every draft to demo4/results/fragnet_runs.json so the site can replay them without a model running.

    python3 demo4/fragnet_test.py --model llama3.1:8b --runs 3
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo4"))
import cpm_ref  # noqa: E402
import fragnet_draft as fd  # noqa: E402

DATA = ROOT / "demo4" / "data"
OUT = ROOT / "demo4" / "results" / "fragnet_runs.json"


def anchors(f, base_ids):
    """The existing activities a fragnet hangs off: (before-ids, after-ids)."""
    pre = sorted({r["pred"] for r in f["relationships"] if r["pred"] in base_ids})
    suc = sorted({r["succ"] for r in f["relationships"] if r["succ"] in base_ids})
    return pre, suc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=fd.MODEL)
    ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()
    sched = json.loads((DATA / "schedule.json").read_text())
    cases = {c["id"]: c for c in json.loads((DATA / "cases.json").read_text())["cases"]}
    key = {k["id"]: k for k in json.loads((DATA / "answer_key.json").read_text())["cases"]}
    base_ids = {x["id"] for x in sched["activities"]}
    crit = cpm_ref.cpm(sched)
    critical = [x["id"] for x in crit["activities"] if x.get("total_float") == 0]
    rows = []
    for cid, c in cases.items():
        truth = c.get("fragnet_truth") or {}
        if not truth.get("activities"):
            continue
        k = key[cid]
        t0 = time.time()
        try:
            d = fd.draft(c["time"]["narrative"], sched["activities"], c["time"].get("claimed_days"), critical, a.model, runs=a.runs)
            r = cpm_ref.tia(sched, d["fragnet"])
            err = None
        except Exception as e:  # noqa: BLE001
            d, r, err = {"fragnet": {"activities": [], "relationships": []}, "agree": False, "notes": []}, None, f"{type(e).__name__}: {e}"
        got = r["delay_calendar_days"] if r else None
        row = {"id": cid, "split": k["split"], "scenario": k["scenario"], "key_delay": k["delay_calendar_days"], "draft_delay": got,
               "key_critical": k["fragnet_critical"], "draft_critical": r["fragnet_critical"] if r else None,
               "delay_exact": got == k["delay_calendar_days"], "delay_within_2": got is not None and abs(got - k["delay_calendar_days"]) <= 2,
               "critical_same": bool(r) and r["fragnet_critical"] == k["fragnet_critical"],
               "links_same": anchors(d["fragnet"], base_ids) == anchors(truth, base_ids),
               "agreed": d.get("agree"), "fragnet": d["fragnet"], "drafts": d.get("drafts"), "notes": d.get("notes"), "error": err,
               "seconds": round(time.time() - t0, 1)}
        rows.append(row)
        print(f"{cid} ({row['split']}): key {row['key_delay']} d, draft {got} d, links {'same' if row['links_same'] else 'differ'}, "
              f"drafts {'agree' if row['agreed'] else 'differ'}{', ERROR ' + err if err else ''}", flush=True)
    summary = {}
    for split in ("dev", "test"):
        rs = [r for r in rows if r["split"] == split]
        summary[split] = {m: sum(bool(r[m]) for r in rs) for m in ("delay_exact", "delay_within_2", "critical_same", "links_same", "agreed")}
        summary[split]["of"] = len(rs)
        # Does agreement predict correctness? (the reason to draft three times)
        summary[split]["exact_when_agreed"] = f"{sum(r['delay_exact'] for r in rs if r['agreed'])}/{sum(1 for r in rs if r['agreed'])}"
        summary[split]["exact_when_disagreed"] = f"{sum(r['delay_exact'] for r in rs if not r['agreed'])}/{sum(1 for r in rs if not r['agreed'])}"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"meta": {"model": a.model, "runs": a.runs, "date": time.strftime("%Y-%m-%d"), "synthetic": True},
                               "summary": summary, "cases": rows}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
