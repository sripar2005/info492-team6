#!/usr/bin/env python3
"""Pre-check sheet: the contract checks that are arithmetic, with the work shown.

For one Change Proposal this builds a sheet of every check that can be computed from a number,
a date, or a signature: what the contract says, what the proposal says, the difference in
dollars where one can be computed, and the clause. Rows that pass are listed too, so a reviewer
who back-checks can see what was verified, not only what failed.

No model is involved. Each check gives the same answer every run.

What is not here, on purpose: anything that turns on what a line item MEANS (is this cost
already covered by the Fee, is the work really a change, is this equipment an Exhibit B or C
item) and anything stated only in a quote that arrived as email text. The sheet says so in a
"not checked" row instead of guessing. Those stay with the agents and with people.

Where the split comes from: our stakeholder told us before Demo 3 that the math is the easy
part, and the Washington State Auditor's change order guidance tells owners to "recalculate
overhead and markup calculations." Which flag types landed on the code side was decided after
the Demo 3 runs, so this is scored beside those results as a separate system. Cases, answer key
and agent prompts are unchanged.

Limit to keep in view: the test proposals are structured data. Real proposals arrive as PDFs
and spreadsheets and must be read into fields first; this file does not do that.

Thresholds come from the contract:
  Section 5.4    labor burden 32%
  Section 6.5.2  sub markup 10% own work / 5% lower tier / 15% total
  Section 6.5.3  Fee 5%, on CM direct costs and subcontractor quotes only
  Section 6.5.4  owned equipment at no more than 75% of Blue Book
  Section 6.5.7  itemized breakdown; T&M tags signed by both parties
  Section 6.2    notice windows by cause (dates from Demo 2's deadline code)
  Exhibit D      $250,000 Owner's Representative approval limit

Usage: python rules.py   (writes results/rules/runs.json and results/checksheets.json)
"""
import json
from pathlib import Path

from calc import sheet

ROOT = Path(__file__).resolve().parent

BURDEN_PERCENT = 32.0
FEE_PERCENT = 5.0
FEE_ALLOWED_ON = ("CM direct costs", "subcontractor quotes")
BLUE_BOOK_PERCENT = 75.0
MARKUP_OWN, MARKUP_LOWER, MARKUP_TOTAL = 10.0, 5.0, 15.0
APPROVAL_LIMIT = 250000

# Cover-sheet field behind each name that can appear in "fee applied to".
FEE_BASE_FIELD = {"NSS items": "nss_items", "SGC items": "sgc_items", "bond and insurance": "bond_and_insurance",
                  "B&O tax": "bo_tax", "permit fees": "permit_fees", "extended SGC (time)": "extended_sgc_time"}

CODE_TYPES = {"SUB_MARKUP", "MISSING_BACKUP", "TIEOUT", "FEE_RATE", "FEE_ON_EXCLUDED", "LABOR_BURDEN",
              "EQUIPMENT", "LATE_NOTICE", "TIME_IMPACT", "CONCEALED_CONDITION", "OVER_AUTHORITY"}
# Always decided by a person. Section 6.2(c), 6.4, Exhibit D.
FORCE_ESCALATE = {"TIME_IMPACT", "CONCEALED_CONDITION", "OVER_AUTHORITY"}
# What the sheet does not check, stated on every sheet.
NOT_COMPUTED = ["Whether a cost is already covered by the Fee (Section 5.5)",
                "Whether the priced work is really a change from the drawings and specs",
                "Whether an equipment item belongs in SGC or NSS (Exhibits B and C)",
                "Whether hours, quantities and unit prices are reasonable"]


def money(x):
    return f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"


def checksheet(cp: dict) -> dict:
    """Every computed check for one CP. status: pass | fail | person | not_checked."""
    s = sheet(cp)
    rows = []

    def row(check, section, status, contract, proposal, flag=None, difference=None, note=None):
        rows.append({"check": check, "section": section, "status": status, "contract": contract,
                     "proposal": proposal, "difference": difference, "flag": flag, "note": note})

    for raw, q in zip(cp["subcontractor_quotes"], s["subcontractors"]):
        firm = q["firm"]
        if q.get("format") == "email text":
            row(f"{firm}: markup, breakdown and totals", "6.5.2, 6.5.7", "not_checked",
                "10% own work, 5% lower tier, 15% total; itemized breakdown",
                "Quote arrived as email text", note="Not read by the calculator. A person or an agent has to read it.")
            continue
        own, low, tot = q["own_work_markup_percent"], q["lower_tier_markup_percent"], q["total_markup_percent_of_direct"]
        over, excess = [], 0.0
        if (own or 0) > MARKUP_OWN:
            over.append(f"{own}% on own work")
            excess += raw["markup_on_own"] - raw["own_direct"] * MARKUP_OWN / 100
        if (low or 0) > MARKUP_LOWER:
            over.append(f"{low}% on lower tier")
            excess += raw["markup_on_lower_tier"] - raw["lower_tier_total"] * MARKUP_LOWER / 100
        if (tot or 0) > MARKUP_TOTAL and not over:
            over.append(f"{tot}% total")
        shown = f"{own}% on own work" + (f", {low}% on lower tier" if low is not None else "")
        row(f"{firm}: markup", "6.5.2", "fail" if over else "pass",
            f"{MARKUP_OWN:g}% own work, {MARKUP_LOWER:g}% lower tier, {MARKUP_TOTAL:g}% total",
            ", ".join(over) if over else shown, flag="SUB_MARKUP" if over else None,
            difference=round(excess, 2) if excess > 0 else None)
        row(f"{firm}: itemized breakdown", "6.5.7", "pass" if q["breakdown_attached"] else "fail",
            "Breakdown of labor, material and equipment attached",
            "Attached" if q["breakdown_attached"] else "Lump sum, no breakdown",
            flag=None if q["breakdown_attached"] else "MISSING_BACKUP")
        if q["tm_tags"]:
            bad = [t["tag"] for t in q["tm_tags"] if not (t["signed_by_cm_superintendent"] and t["signed_by_owner_rep"])]
            row(f"{firm}: T&M tags signed", "6.5.7", "fail" if bad else "pass",
                "Signed by CM superintendent and Owner's Representative",
                f"Unsigned: {', '.join(bad)}" if bad else f"{len(q['tm_tags'])} of {len(q['tm_tags'])} signed",
                flag="MISSING_BACKUP" if bad else None)
        adds = q["lines_add_up_to_quote_direct"] is not False and q["lower_tier_adds_up"]
        if q["breakdown_attached"]:
            row(f"{firm}: lines add up", "6.5", "pass" if adds else "fail", "Lines sum to the quoted direct cost",
                "They do" if adds else "They do not", flag=None if adds else "TIEOUT")

    c, cov = s["cover"], cp["cover_sheet"]
    diff = c["difference_total_minus_lines"]
    row("Cover sheet ties out", "6.5", "fail" if abs(diff) > 1 else "pass",
        f"Lines sum to {money(c['sum_of_cover_lines'])}", f"Total requested {money(c['total_requested'])}",
        flag="TIEOUT" if abs(diff) > 1 else None, difference=diff if abs(diff) > 1 else None)

    base = cov["cm_direct_costs"] + cov["subcontractor_quotes"]
    rate_ok = c["fee_rate_percent"] == FEE_PERCENT
    row("Fee rate", "6.5.3", "pass" if rate_ok else "fail", f"{FEE_PERCENT:g}%", f"{c['fee_rate_percent']:g}%",
        flag=None if rate_ok else "FEE_RATE",
        difference=None if rate_ok else round((c["fee_rate_percent"] - FEE_PERCENT) / 100 * base, 2))
    excluded = [p for p in c["fee_applied_to"] if p not in FEE_ALLOWED_ON]
    fee_on_excl = round(sum(cov.get(FEE_BASE_FIELD.get(p, ""), 0) for p in excluded) * cov["fee_rate"], 2)
    row("Fee base", "6.5.3", "fail" if excluded else "pass", "Fee on CM direct costs and subcontractor quotes only",
        f"Fee also taken on {', '.join(excluded)}" if excluded else "Fee on CM direct costs and subcontractor quotes",
        flag="FEE_ON_EXCLUDED" if excluded else None, difference=fee_on_excl if excluded and fee_on_excl else None)

    for raw, l in zip(cp["cm_lines"], s["cm_lines"]):
        b = l.get("burden_percent")
        if b is not None:
            ok = b == BURDEN_PERCENT
            row(f"Labor burden: {l['desc']}", "5.4", "pass" if ok else "fail", f"{BURDEN_PERCENT:g}%", f"{b:g}%",
                flag=None if ok else "LABOR_BURDEN",
                difference=None if ok else round(raw["hours"] * raw["wage"] * (b - BURDEN_PERCENT) / 100, 2))
        bb = l.get("rate_as_percent_of_blue_book")
        if bb is not None:
            ok = bb <= BLUE_BOOK_PERCENT
            row(f"Owned equipment rate: {l['desc']}", "6.5.4", "pass" if ok else "fail",
                f"No more than {BLUE_BOOK_PERCENT:g}% of Blue Book", f"{bb:g}% of Blue Book",
                flag=None if ok else "EQUIPMENT")

    n = s["notice"]
    row("Notice on time", n["notice_rule_for_cause_type"], "pass" if n["notice_on_time"] else "fail",
        f"Due {n['notice_due']} ({n['cause_type']} on {n['event_date']})", f"Given {n['notice_date']}",
        flag=None if n["notice_on_time"] else "LATE_NOTICE")

    days = c["extended_sgc_days"]
    row("Time claim", "6.4", "person" if days > 0 else "pass", "A claim for time is decided by a person",
        f"{days} days claimed" if days > 0 else "No time claimed", flag="TIME_IMPACT" if days > 0 else None)
    concealed = cp["cause"]["type"] == "Concealed condition"
    row("Site condition", "6.2(c)", "person" if concealed else "pass", "Entitlement for a concealed condition is decided by a person",
        "Cause is a concealed condition" if concealed else f"Cause: {cp['cause']['type']}",
        flag="CONCEALED_CONDITION" if concealed else None)
    row("Approval limit", "Exhibit D", "person" if c["over_250000"] else "pass",
        f"Owner's Representative may approve up to {money(APPROVAL_LIMIT)}", f"Total requested {money(c['total_requested'])}",
        flag="OVER_AUTHORITY" if c["over_250000"] else None)

    count = {k: sum(1 for r in rows if r["status"] == k) for k in ("pass", "fail", "person", "not_checked")}
    at_issue = round(sum(r["difference"] for r in rows if r["status"] == "fail" and r["difference"] and r["difference"] > 0), 2)
    types = {r["flag"] for r in rows if r["flag"]}
    route = "ESCALATE" if types & FORCE_ESCALATE else "RETURN" if types else "APPROVE"
    result = {"APPROVE": "Computed checks pass", "RETURN": "Return for correction", "ESCALATE": "Goes to a person"}[route]
    return {"id": cp["id"], "title": cp["title"], "total_requested": cp["cover_sheet"]["total_requested"],
            "route": route, "result": result, "counts": count, "dollars_at_issue": at_issue, "rows": rows,
            "not_computed": NOT_COMPUTED}


def check(cp: dict) -> dict:
    """Scoring view of the sheet: one flag per failed or person row, in the run format evaluate.py reads."""
    cs = checksheet(cp)
    flags = [{"type": r["flag"], "section": r["section"], "explanation": f"{r['check']}: {r['proposal']} (contract: {r['contract']})",
              "amount_at_issue": r["difference"], "basis": "computed"} for r in cs["rows"] if r["flag"]]
    unparsed = [q["firm"] for q in cp["subcontractor_quotes"] if q.get("format") == "email text"]
    env = {"envelope_id": f"{cp['id']}-rules", "from_role": "rules", "authority": "computes, never decides",
           "decision": {"APPROVE": "PASS"}.get(cs["route"], cs["route"]), "flags": flags,
           "unparsed_quotes": unparsed, "model": "computed contract checks"}
    return {"id": cp["id"], "route": cs["route"], "trail": [env]}


def main():
    cases = json.loads((ROOT / "data" / "cases.json").read_text())["cases"]
    out = ROOT / "results" / "rules" / "runs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": {"backend": "rules", "model": "computed contract checks"},
                               "results": [check(c) for c in cases]}, indent=1))
    sheets = {c["id"]: checksheet(c) for c in cases}
    (ROOT / "results" / "checksheets.json").write_text(json.dumps({"sheets": sheets}, indent=1))
    print(f"Saved {out} and results/checksheets.json")


if __name__ == "__main__":
    main()
