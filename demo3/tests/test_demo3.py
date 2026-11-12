#!/usr/bin/env python3
"""Offline checks for Demo 3 (no API calls). Run from demo3/: python tests/test_demo3.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from calc import sheet  # noqa: E402
from evaluate import score  # noqa: E402
import agents  # noqa: E402

cases = {c["id"]: c for c in json.loads((ROOT / "data" / "cases.json").read_text())["cases"]}
key = json.loads((ROOT / "data" / "answer_key.json").read_text())["cases"]
assert len(cases) == 36 and all("expected_flags" not in json.dumps(c) for c in cases.values()), "agents must not see labels"

# Calculator facts behind seeded issues
assert sheet(cases["CP-0209"])["subcontractors"][0]["own_work_markup_percent"] == 15.0
assert sheet(cases["CP-0210"])["subcontractors"][0]["lower_tier_markup_percent"] == 10.0
assert sheet(cases["CP-0220"])["cover"]["difference_total_minus_lines"] == 1800.0
assert sheet(cases["CP-0222"])["notice"]["notice_due"] == "2020-03-09" and not sheet(cases["CP-0222"])["notice"]["notice_on_time"]
assert sheet(cases["CP-0229"])["notice"]["notice_due"] == "2020-05-26", "Memorial Day roll-forward"
assert sheet(cases["CP-0226"])["cover"]["over_250000"]
assert sheet(cases["CP-0204"])["cover"]["fee_as_percent_of_direct_plus_subs"] == 5.0, "deductive fee at 5%"
for cid in ("CP-0201", "CP-0207", "CP-0208"):
    assert sheet(cases[cid])["cover"]["difference_total_minus_lines"] == 0.0
print("calculator ok")

# Sub agent sees only its own pricing
v = agents.view_for("sub", cases["CP-0211"])
assert "cm_lines" not in v and "cover_sheet" not in v
print("role views ok")

# Scoring: a perfect run, then known errors
def env(role, decision, types):
    return {"from_role": role, "decision": decision, "flags": [{"type": t, "quote_verified": True} for t in types]}
perfect = {"results": []}
for k in key:
    ft = {}
    for f in k["expected_flags"]:
        ft.setdefault(f["role"], []).append(f["type"])
    dec = {"APPROVE": "PASS"}.get(k["expected_route"], k["expected_route"])
    perfect["results"].append({"id": k["id"], "route": k["expected_route"],
                               "trail": [env(r, dec, ft.get(r, [])) for r in agents.ROLES]})
m = score(perfect, key)["metrics"]
assert m["detection_rate"] == 1 and m["route_accuracy"] == 1 and m["extra_flags"] == 0 and m["caught_by_responsible_party"] == 33
bad = json.loads(json.dumps(perfect))
r = {x["id"]: x for x in bad["results"]}
r["CP-0209"]["trail"] = [env("owner", "PASS", [])]; r["CP-0209"]["route"] = "APPROVE"          # missed sub markup
r["CP-0201"]["trail"] = [env("owner", "RETURN", ["COVERED_COST"])]; r["CP-0201"]["route"] = "RETURN"  # false alarm
m = score(bad, key)["metrics"]
assert m["issues_caught"] == 32 and m["extra_flags"] == 1 and m["clean_cases_flagged"] == 1 and m["routes_right"] == 34
print("scoring ok\nAll offline tests passed.")
