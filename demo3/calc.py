"""Calculator sheet for a Change Proposal: arithmetic only, no judgments.

The agents decide which contract rules apply and whether a number breaks them. This module only
adds things up, computes percentages, and counts days, so no agent has to do arithmetic. The same
split as Demo 2 (agent judges, code computes dates), now extended to money.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "demo2"))
from deadlines import notice_due  # noqa: E402

NOTICE_RULE = {"RFI response": "6.2(a)", "ASI": "6.2(a)", "Submittal return": "6.2(a)",
               "Owner direction": "6.2(b)", "Architect direction": "6.2(b)",
               "Concealed condition": "6.2(c)", "Other event": "6.2(d)"}


def pct(a, b):
    return round(100 * a / b, 2) if b else None


def sheet(cp: dict) -> dict:
    """Return computed facts for one CP package."""
    out = {"subcontractors": [], "cm_lines": [], "cover": {}, "notice": {}}
    for q in cp["subcontractor_quotes"]:
        if q.get("format") == "email text":
            out["subcontractors"].append({"firm": q["firm"], "format": "email text",
                                          "note": "Quote arrived as free text; the calculator did not parse it.",
                                          "quote_total": q["quote_total"]})
            continue
        line_sum = round(sum(l["amount"] for l in q["lines"]), 2) if q["lines"] else None
        low_sum = round(sum(l["amount"] for l in q["lower_tier"]), 2) if q["lower_tier"] else 0.0
        out["subcontractors"].append({
            "firm": q["firm"],
            "own_work_markup_percent": pct(q["markup_on_own"], q["own_direct"]),
            "lower_tier_markup_percent": pct(q["markup_on_lower_tier"], q["lower_tier_total"]),
            "total_markup_percent_of_direct": pct(q["markup_on_own"] + q["markup_on_lower_tier"], q["own_direct"] + q["lower_tier_total"]),
            "breakdown_attached": bool(q["lines"]),
            "lines_add_up_to_quote_direct": (abs(line_sum - q["own_direct"]) < 0.01) if line_sum is not None else None,
            "lower_tier_adds_up": abs(low_sum - q["lower_tier_total"]) < 0.01,
            "tm_tags": [{"tag": t["tag"], "signed_by_cm_superintendent": t["signed_by_cm_superintendent"],
                         "signed_by_owner_rep": t["signed_by_owner_rep"]} for t in q.get("tm_tags", [])],
        })
    for l in cp["cm_lines"]:
        f = {"desc": l["desc"], "kind": l["kind"], "amount": l["amount"]}
        if l["kind"] == "labor":
            f["burden_percent"] = round(100 * l["burden_rate"], 1)
        if l["kind"] == "equipment" and "blue_book_rate" in l:
            f["rate_as_percent_of_blue_book"] = pct(l["rate_charged"], l["blue_book_rate"])
        out["cm_lines"].append(f)
    c = cp["cover_sheet"]
    parts = (c["cm_direct_costs"] + c["subcontractor_quotes"] + c["fee"] + c["bond_and_insurance"] + c["bo_tax"]
             + c["permit_fees"] + c["nss_items"] + c["sgc_items"] + c["extended_sgc_time"])
    direct_and_subs = c["cm_direct_costs"] + c["subcontractor_quotes"]
    out["cover"] = {
        "sum_of_cover_lines": round(parts, 2),
        "total_requested": c["total_requested"],
        "difference_total_minus_lines": round(c["total_requested"] - parts, 2),
        "fee_rate_percent": round(100 * c["fee_rate"], 2),
        "fee_applied_to": c["fee_applied_to"],
        "fee_as_percent_of_direct_plus_subs": pct(c["fee"], direct_and_subs),
        "extended_sgc_days": cp["time_impact_days"],
        "over_250000": c["total_requested"] > 250000,
    }
    rule = NOTICE_RULE[cp["cause"]["type"]]
    due = notice_due(cp["cause"]["event_date"], rule)
    out["notice"] = {"cause_type": cp["cause"]["type"], "event_date": cp["cause"]["event_date"],
                     "notice_date": cp["notice_date"], "notice_rule_for_cause_type": rule, "notice_due": due,
                     "notice_on_time": cp["notice_date"] <= due, "costs_incurred_from": cp.get("costs_incurred_from")}
    return out
