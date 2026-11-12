#!/usr/bin/env python3
"""Rule-and-keyword baseline for Demo 3: no AI.

Uses the same calculator sheet the agents get, fixed thresholds from the contract, and keyword lists
copied from the contract's own lists (Section 5.5, Exhibit B, Exhibit C). If the agents can't beat
this, the agents aren't adding value on these cases.

Usage: python baseline.py   (writes results/baseline/runs.json)
"""
import json
from pathlib import Path

from calc import sheet

ROOT = Path(__file__).resolve().parent
# Keywords taken from the contract's lists, written before looking at any agent output.
COVERED_WORDS = ["project manager", "superintendent", "project engineer", "estimat", "home office", "accounting",
                 "purchasing", "executive", "pricing", "negotiat", "field office"]
EQUIP_SGC_WORDS = ["pickup", "vehicle", "small tool", "hand tool", "trailer"]
EQUIP_NSS_WORDS = ["crane", "hoist"]
NOT_CHANGE_WORDS = ["no change", "already in the contract"]  # generic phrases, not tuned to the cases


def check(cp):
    s = sheet(cp)
    flags = []
    def f(t, why):
        flags.append({"type": t, "section": "", "quote": "", "explanation": why, "quote_verified": False})
    for q in s["subcontractors"]:
        if q.get("format") == "email text":
            continue  # a rules engine reads structured fields only
        if (q["own_work_markup_percent"] or 0) > 10 or (q["lower_tier_markup_percent"] or 0) > 5 or (q["total_markup_percent_of_direct"] or 0) > 15:
            f("SUB_MARKUP", f"{q['firm']} markup over limit")
        if not q["breakdown_attached"] or any(not t["signed_by_owner_rep"] or not t["signed_by_cm_superintendent"] for t in q["tm_tags"]):
            f("MISSING_BACKUP", f"{q['firm']} missing breakdown or signatures")
        if q["lines_add_up_to_quote_direct"] is False or not q["lower_tier_adds_up"]:
            f("TIEOUT", f"{q['firm']} quote lines do not add up")
    c = s["cover"]
    if abs(c["difference_total_minus_lines"]) > 1:
        f("TIEOUT", "cover total differs from its lines")
    if c["fee_rate_percent"] != 5.0:
        f("FEE_RATE", "fee rate is not 5%")
    if any(p not in ("CM direct costs", "subcontractor quotes") for p in c["fee_applied_to"]):
        f("FEE_ON_EXCLUDED", "fee applied beyond direct costs and subs")
    text = (cp["narrative"] + " " + " ".join(l["desc"] for l in cp["cm_lines"])).lower()
    if any(w in text for w in COVERED_WORDS):
        f("COVERED_COST", "covered-cost keyword")
    for l in s["cm_lines"]:
        if l.get("burden_percent") not in (None, 32.0):
            f("LABOR_BURDEN", "burden is not 32%")
        if (l.get("rate_as_percent_of_blue_book") or 0) > 75:
            f("EQUIPMENT", "owned equipment over 75% of Blue Book")
    if any(w in text for w in EQUIP_SGC_WORDS + EQUIP_NSS_WORDS):
        f("EQUIPMENT", "equipment keyword from Exhibit B or C")
    if not s["notice"]["notice_on_time"]:
        f("LATE_NOTICE", "notice after due date")
    if any(w in (cp["narrative"] + " " + cp["scope_context"]).lower() for w in NOT_CHANGE_WORDS):
        f("NOT_A_CHANGE", "scope keyword")
    if c["extended_sgc_days"] > 0:
        f("TIME_IMPACT", "time claimed")
    if cp["cause"]["type"] == "Concealed condition":
        f("CONCEALED_CONDITION", "concealed condition")
    if c["over_250000"]:
        f("OVER_AUTHORITY", "over $250,000")
    # one flag per type
    seen, uniq = set(), []
    for x in flags:
        if x["type"] not in seen:
            seen.add(x["type"]); uniq.append(x)
    esc = {"TIME_IMPACT", "CONCEALED_CONDITION", "OVER_AUTHORITY"}
    route = "ESCALATE" if seen & esc else "RETURN" if seen else "APPROVE"
    env = {"envelope_id": f"{cp['id']}-baseline", "from_role": "baseline", "decision": {"APPROVE": "PASS"}.get(route, route),
           "flags": uniq, "message": "", "model": "rules + keywords"}
    return {"id": cp["id"], "route": route, "trail": [env]}


def main():
    cases = json.loads((ROOT / "data" / "cases.json").read_text())["cases"]
    out = ROOT / "results" / "baseline" / "runs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": {"backend": "baseline", "model": "rules + keywords"},
                               "results": [check(c) for c in cases]}, indent=1))
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
