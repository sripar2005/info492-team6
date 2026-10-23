#!/usr/bin/env python3
"""Convert Yousuf Shaik's Demo 2 test set (yousuf_cases.json, written independently of the classifier)
into the classifier's input format. His labels, reasons, and dates are kept exactly; nothing is relabeled.

Outputs (in this folder):
  cases.json        what the classifier sees: type, sender, date, text. No labels.
  answer_key.json   his labels mapped to the evaluator's fields.

Also checks that every notice_due he gave equals the date computed from his stated rule:
7 calendar days after receipt, rolled to the next business day past weekends and US federal holidays.
Run: python data/set_b/convert.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from deadlines import notice_due  # noqa: E402

src = json.loads((HERE / "yousuf_cases.json").read_text(encoding="utf-8"))
cases, key = [], []
for c in src["cases"]:
    label = {"clarification": "CLARIFICATION", "change": "POSSIBLE CHANGE"}[c["label"]]
    rule = c["notice_clause"] or "none"
    computed = notice_due(c["received"], rule, calendar="us_federal") if label == "POSSIBLE CHANGE" else None
    assert computed == c["notice_due"], (c["id"], c["notice_due"], computed)
    cases.append({"id": c["id"], "source": c["source_type"], "event_date": c["received"], "from": c["sender"], "text": c["message"]})
    key.append({"id": c["id"], "label": label, "notice_rule": rule, "sections": [c["notice_clause"]] if c["notice_clause"] else [],
                "notice_due": c["notice_due"], "tricky": c["difficulty"] == "subtle", "why": c["reason"]})
(HERE / "cases.json").write_text(json.dumps({"cases": cases}, indent=2) + "\n", encoding="utf-8")
(HERE / "answer_key.json").write_text(json.dumps({
    "meta": {"author": "Yousuf Shaik", "source_file": "yousuf_cases.json", "holiday_calendar": "us_federal",
             "status": src["meta"].get("status", "")},
    "cases": key}, indent=2) + "\n", encoding="utf-8")
print(f"OK: {len(cases)} cases converted; all {sum(k['notice_due'] is not None for k in key)} deadlines match the stated rule.")
