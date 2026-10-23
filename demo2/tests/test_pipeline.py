#!/usr/bin/env python3
"""Offline tests for Demo 2 (no API key needed). Run from the demo2 folder: python tests/test_pipeline.py"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from deadlines import notice_due  # noqa: E402
from evaluate import evaluate  # noqa: E402

# Deadline rules (Section 6.2 + Section 1.4 roll-forward)
assert notice_due("2020-02-18", "6.2(a)") == "2020-02-25"
assert notice_due("2020-07-07", "6.2(d)") == "2020-07-21"
assert notice_due("2020-02-15", "6.2(c)") == "2020-02-24", "Saturday +7 = Saturday, rolls to Monday"
assert notice_due("2020-05-18", "6.2(a)") == "2020-05-26", "Memorial Day rolls to Tuesday"
assert notice_due("2020-02-18", "none") is None
print("deadline rules ok")

cases = json.loads((ROOT / "data" / "cases.json").read_text())["cases"]
key = json.loads((ROOT / "data" / "answer_key.json").read_text())["cases"]
assert len(cases) == 30 and all("label" not in c for c in cases), "the model's input must not contain labels"
print("cases ok: 30, no labels in model input")


def perfect_run():
    res = []
    for k in key:
        res.append({"id": k["id"], "answer": {"label": k["label"], "notice_rule": k["notice_rule"], "notice_due": k["notice_due"],
                                               "sections": k["sections"], "quote": "x", "reasoning": "x"},
                    "quote_verified": True, "computed_notice_due": k["notice_due"]})
    return {"results": res}


m = evaluate(cases, key, perfect_run())["metrics"]
assert m["label_accuracy"] == 1 and m["change_recall"] == 1 and m["deadline_accuracy_code_date"] == 1 and m["meets_target"]
print("perfect run scores 100%: ok")

# Known errors: 2 missed changes, 1 false alarm, 1 wrong rule, 1 wrong model date, 1 unverified quote
run = perfect_run()
by = {r["id"]: r for r in run["results"]}
for cid in ["P02", "P08"]:
    by[cid]["answer"].update(label="CLARIFICATION", notice_rule="none", notice_due=None); by[cid]["computed_notice_due"] = None
by["C13"]["answer"].update(label="POSSIBLE CHANGE", notice_rule="6.2(b)", notice_due="2020-07-21"); by["C13"]["computed_notice_due"] = "2020-07-21"
by["P09"]["answer"]["notice_rule"] = "6.2(a)"; by["P09"]["computed_notice_due"] = notice_due("2020-07-07", "6.2(a)")
by["P06"]["answer"]["notice_due"] = "2020-02-22"   # model forgets the weekend roll; code date still right
by["C01"]["quote_verified"] = False
r = evaluate(cases, key, run)
m = r["metrics"]
c = m["confusion"]
assert (c["missed_change"], c["false_alarm"]) == (2, 1), c
assert abs(m["label_accuracy"] - 27 / 30) < 1e-9
assert m["rule_scored_on"] == 13 and abs(m["notice_rule_accuracy"] - 12 / 13) < 1e-9
assert abs(m["deadline_accuracy_model_date"] - 12 / 13) < 1e-9  # only P06 wrong (P09 kept its date)
assert abs(m["deadline_accuracy_code_date"] - 12 / 13) < 1e-9  # only P09 (wrong rule) wrong
assert abs(m["citation_validity"] - 29 / 30) < 1e-9
outcomes = {t["id"]: t["outcome"] for t in r["trace"]}
assert outcomes["P02"] == "missed change" and outcomes["C13"] == "false alarm" and outcomes["P09"] == "right label, wrong deadline"
print("known errors counted correctly: ok")
print("\nAll offline tests passed.")

# Set B (Yousuf's independently written cases): converted without relabeling, deadlines match his stated rule
b_cases = json.loads((ROOT / "data" / "set_b" / "cases.json").read_text())["cases"]
b_key = json.loads((ROOT / "data" / "set_b" / "answer_key.json").read_text())["cases"]
src = {c["id"]: c for c in json.loads((ROOT / "data" / "set_b" / "yousuf_cases.json").read_text())["cases"]}
assert len(b_cases) == 30 and all("label" not in c for c in b_cases)
for k in b_key:
    s = src[k["id"]]
    assert k["label"] == {"clarification": "CLARIFICATION", "change": "POSSIBLE CHANGE"}[s["label"]] and k["notice_due"] == s["notice_due"] and k["why"] == s["reason"]
    if s["notice_due"]:
        assert notice_due(s["received"], s["notice_clause"], "us_federal") == s["notice_due"]
print("set B ok: 30 cases, labels unchanged from Yousuf's file, deadlines verified")
