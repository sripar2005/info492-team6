#!/usr/bin/env python3
"""Demo 3 test data: 36 priced Change Proposals (CPs) on Demo 1's synthetic contract.

Each CP is a package a subcontractor, the GC/CM, the Architect, and the Owner's PM would all see:
the cause (RFI response, ASI, direction, condition), dates, subcontractor quotes with line items,
the CM's own cost lines, and a cover sheet with markups and Fee.

The cover sheet is computed from the lines, so every number ties out unless a case deliberately
breaks it. Violations are seeded by changing one input (a markup rate, a line that shouldn't be
there, a missing signature), and the answer key records exactly what was seeded.

Writes:
  data/cases.json        what the agents see (no labels)
  data/answer_key.json   seeded violations, the role that should catch each, and the expected route

Run from the demo3 folder: python data/build_cases.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / "demo2"))
from deadlines import notice_due  # noqa: E402  (Demo 2's Section 6.2 + 1.4 date code)

BURDEN = 0.32          # Section 5.4 fixed labor burden
FEE = 0.05             # Section 6.5.3
SGC_DAILY = 3185       # Section 5.2
NOTICE_RULE = {"RFI response": "6.2(a)", "ASI": "6.2(a)", "Submittal return": "6.2(a)",
               "Owner direction": "6.2(b)", "Architect direction": "6.2(b)",
               "Concealed condition": "6.2(c)", "Other event": "6.2(d)"}

# Who should catch each violation type (the party whose agent is responsible for it).
RESPONSIBLE = {
    "SUB_MARKUP": "gc", "MISSING_BACKUP": "gc", "TIEOUT": "gc",
    "FEE_ON_EXCLUDED": "owner", "FEE_RATE": "owner", "COVERED_COST": "owner", "EQUIPMENT": "owner",
    "LABOR_BURDEN": "owner", "LATE_NOTICE": "owner", "NOT_A_CHANGE": "architect",
    "TIME_IMPACT": "owner", "CONCEALED_CONDITION": "owner", "OVER_AUTHORITY": "owner",
}
ESCALATION_TYPES = {"TIME_IMPACT", "CONCEALED_CONDITION", "OVER_AUTHORITY"}


def r2(x):
    return round(x + 1e-9, 2)


def sub(name, trade, own, lower=(), own_pct=0.10, lower_pct=0.05, breakdown=True, tm_tags=None):
    """A subcontractor quote. own = [(desc, qty, unit, rate)], lower = [(lower-tier firm, scope, amount)]."""
    lines = [{"desc": d, "qty": q, "unit": u, "rate": rt, "amount": r2(q * rt)} for d, q, u, rt in own]
    own_direct = r2(sum(l["amount"] for l in lines))
    lower_lines = [{"firm": f, "scope": s, "amount": a} for f, s, a in lower]
    lower_total = r2(sum(l["amount"] for l in lower_lines))
    own_mk, low_mk = r2(own_direct * own_pct), r2(lower_total * lower_pct)
    q = {"firm": name, "trade": trade, "markup_rates_stated": {"own_work": own_pct, "lower_tier": lower_pct},
         "own_direct": own_direct, "lower_tier_total": lower_total, "markup_on_own": own_mk,
         "markup_on_lower_tier": low_mk, "quote_total": r2(own_direct + lower_total + own_mk + low_mk)}
    if breakdown:
        q["lines"], q["lower_tier"] = lines, lower_lines
    else:
        q["lines"], q["lower_tier"] = [], []
        q["note"] = "Lump-sum quote. No breakdown attached."
    if tm_tags is not None:
        q["tm_tags"] = tm_tags
    return q


def as_email(q, opener, extra=""):
    """Turn a structured quote into the free-text email a sub actually sends (no parsed fields)."""
    rows = [f"  - {l['desc']}: {l['qty']} {l['unit']} x ${l['rate']:,.2f} = ${l['amount']:,.2f}" for l in q["lines"]]
    rows += [f"  - {l['firm']} ({l['scope']}): ${l['amount']:,.2f}" for l in q["lower_tier"]]
    r = q["markup_rates_stated"]
    mk = f"OH&P {r['own_work'] * 100:g}% on our work (${q['markup_on_own']:,.2f})"
    if q["lower_tier_total"]:
        mk += f", {r['lower_tier'] * 100:g}% on {q['lower_tier'][0]['firm']} (${q['markup_on_lower_tier']:,.2f})"
    body = (f"{opener}\n\n" + "\n".join(rows) + f"\n\nSubtotal ${q['own_direct'] + q['lower_tier_total']:,.2f}. {mk}. "
            f"Total ${q['quote_total']:,.2f}.{(' ' + extra) if extra else ''}\n\nThanks,\n{q['firm']} estimating")
    return {"firm": q["firm"], "trade": q["trade"], "format": "email text", "text": body, "quote_total": q["quote_total"],
            "lines": [], "lower_tier": [], "own_direct": None, "lower_tier_total": None,
            "markup_on_own": None, "markup_on_lower_tier": None}


def labor(desc, hours, wage, burden=BURDEN, who=None):
    l = {"kind": "labor", "desc": desc, "hours": hours, "wage": wage, "burden_rate": burden,
         "amount": r2(hours * wage * (1 + burden))}
    if who:
        l["person"] = who
    return l


def equip(desc, hours, bluebook, pct=0.75, owned=True, idle_hours=0, log=True):
    rate = r2(bluebook * pct)
    amt = r2(hours * rate + idle_hours * rate * 0.5)
    return {"kind": "equipment", "desc": desc, "owned_by_cm": owned, "hours_used": hours, "idle_hours": idle_hours,
            "blue_book_rate": bluebook, "rate_charged": rate, "amount": amt, "daily_logs_attached": log}


def rented(desc, invoice):
    return {"kind": "equipment", "desc": desc, "owned_by_cm": False, "rental_invoice": invoice, "amount": invoice,
            "daily_logs_attached": True}


def line(kind, desc, amount):
    return {"kind": kind, "desc": desc, "amount": amount}


def build(cp, title, cause_type, cause_ref, cause_date, notice_date, submitted, narrative, scope_context,
          subs=(), cm=(), fee_rate=FEE, fee_on=("direct", "subs"), time_days=0, cover_adjust=0.0,
          costs_from=None, backup=None):
    """Assemble a CP package and its cover sheet from the lines."""
    cm = list(cm)
    direct = r2(sum(l["amount"] for l in cm if l["kind"] in ("labor", "equipment", "material")))
    subs_total = r2(sum(s["quote_total"] for s in subs))
    no_fee = {k: r2(sum(l["amount"] for l in cm if l["kind"] == k)) for k in ("bond_insurance", "bo_tax", "permit", "nss", "sgc")}
    time_amount = r2(time_days * SGC_DAILY)
    fee_base = 0.0
    fee_base_parts = []
    for part in fee_on:
        if part == "direct":
            fee_base += direct; fee_base_parts.append("CM direct costs")
        elif part == "subs":
            fee_base += subs_total; fee_base_parts.append("subcontractor quotes")
        elif part == "time":
            fee_base += time_amount; fee_base_parts.append("extended SGC (time)")
        else:
            fee_base += no_fee[part]; fee_base_parts.append({"bond_insurance": "bond and insurance", "bo_tax": "B&O tax",
                                                               "permit": "permit fees", "nss": "NSS items", "sgc": "SGC items"}[part])
    fee_base = r2(fee_base)
    fee_amt = r2(fee_base * fee_rate)
    total = r2(direct + subs_total + sum(no_fee.values()) + time_amount + fee_amt + cover_adjust)
    rule = NOTICE_RULE[cause_type]
    pkg = {
        "id": cp, "title": title,
        "cause": {"type": cause_type, "reference": cause_ref, "event_date": cause_date},
        "notice_date": notice_date, "cp_submitted": submitted,
        "narrative": narrative,
        "scope_context": scope_context,
        "subcontractor_quotes": list(subs),
        "cm_lines": cm,
        "time_impact_days": time_days,
        "cover_sheet": {
            "cm_direct_costs": direct,
            "subcontractor_quotes": subs_total,
            "fee_rate": fee_rate,
            "fee_applied_to": fee_base_parts,
            "fee": fee_amt,
            "bond_and_insurance": no_fee["bond_insurance"], "bo_tax": no_fee["bo_tax"], "permit_fees": no_fee["permit"],
            "nss_items": no_fee["nss"], "sgc_items": no_fee["sgc"],
            "extended_sgc_time": time_amount,
            "total_requested": total,
        },
        "backup_attached": backup or ["cause document", "subcontractor quotes with breakdowns"],
    }
    if costs_from:
        pkg["costs_incurred_from"] = costs_from
    return pkg, rule


CASES = []


def add(pkg_rule, expect, route, why, tricky=False):
    pkg, rule = pkg_rule
    pkg["_rule"] = rule
    CASES.append((pkg, [{"type": t, "role": RESPONSIBLE[t], "detail": d} for t, d in expect], route, why, tricky))


# ---------------------------------------------------------------- clean cases (8)
add(build("CP-0201", "Gym roof drains added per RFI-112", "RFI response", "RFI-112", "2020-02-10", "2020-02-14", "2020-02-28",
          "RFI-112 response adds two overflow roof drains at the gym roof. Plumbing sub to furnish and install.",
          "Drawing P-201 shows four primary roof drains at the gym; no overflow drains are shown.",
          subs=[sub("Cascade Plumbing", "Plumbing", [("Overflow roof drain body and dome", 2, "ea", 640.0), ("4\" cast iron leader and fittings", 86, "lf", 31.0), ("Plumber", 22, "hr", 92.0)])]),
    [], "APPROVE", "Markups, Fee, and notice all within the contract.")

add(build("CP-0202", "Fire-rated door hardware per ASI-014", "ASI", "ASI-014", "2020-03-02", "2020-03-06", "2020-03-20",
          "ASI-014 changes eight corridor doors to 90-minute assemblies with fire-rated hardware. ASI says no change in cost or time; CM gave notice that it adds cost.",
          "Spec 08 71 00 lists standard (non-rated) hardware sets for corridor doors C101 to C108.",
          subs=[sub("Northwest Door & Hardware", "Doors and hardware", [("Fire-rated hardware set", 8, "ea", 415.0), ("Door installer", 16, "hr", 78.0)])]),
    [], "APPROVE", "The ASI adds rated hardware not in the spec; notice was on time and pricing follows 6.5.")

add(build("CP-0203", "Library data drops per Owner email", "Owner direction", "Owner email 2020-04-06", "2020-04-06", "2020-04-09", "2020-04-24",
          "Owner's Representative directed 24 added data drops in the library. Electrical sub with low-voltage lower-tier.",
          "Drawing T-101 shows 12 data drops in the library.",
          subs=[sub("Sound Electric", "Electrical", [("Electrician", 30, "hr", 96.0), ("Box, ring, conduit per drop", 24, "ea", 38.0)],
                    lower=[("Lakeside Low Voltage", "Cat 6 cabling, termination, testing", 7200.0)])]),
    [], "APPROVE", "Sub took 10% on its own work and 5% on the lower-tier, within 6.5.2.")

add(build("CP-0204", "Delete covered walkway canopy (deductive)", "Owner direction", "Owner letter 2020-05-04", "2020-05-04", "2020-05-07", "2020-05-20",
          "Owner deleted the covered walkway canopy at the bus loop. Credit from steel sub; Fee reduced at 5%.",
          "Drawing S-401 shows a 60-foot steel canopy at the bus loop.",
          subs=[sub("Puget Steel Erectors", "Structural steel", [("Canopy steel, fabricated (credit)", 1, "ls", -38500.0), ("Erection crew (credit)", 120, "hr", -88.0)])]),
    [], "APPROVE", "Deductive change; Fee is reduced at the same 5% rate, as 6.5.3 requires.", tricky=True)

add(build("CP-0205", "Heavier stud gauge per submittal return", "Submittal return", "Submittal 09 22 16-02 (Approved as Noted)", "2020-05-11", "2020-05-15", "2020-05-29",
          "Architect's comment on the framing submittal requires 18-gauge studs at the gym in place of 20-gauge. Framing sub prices the difference; CM rented a scissor lift.",
          "Spec 09 22 16 allows 20-gauge studs for interior partitions up to 14 feet.",
          subs=[sub("Evergreen Framing", "Framing and drywall", [("18 ga stud upcharge", 1, "ls", 6150.0), ("Framer", 40, "hr", 74.0)])],
          cm=[rented("Scissor lift rental, 1 week", 1180.0)]),
    [], "APPROVE", "Comment changes cost; notice under 6.2(a) via 8.3 on time; rented equipment at invoice.")

add(build("CP-0206", "Hallway ceiling access panels, T&M", "RFI response", "RFI-131", "2020-06-01", "2020-06-04", "2020-06-17",
          "RFI-131 response adds 14 access panels. Done on T&M; the CM superintendent and Owner's Representative signed every tag. The tower crane was not used.",
          "Reflected ceiling plan A-501 shows no access panels in corridors.",
          subs=[sub("Evergreen Framing", "Framing and drywall", [("Access panel 24x24", 14, "ea", 165.0), ("Drywall finisher", 21, "hr", 72.0)],
                    tm_tags=[{"tag": f"TM-{n}", "date": "2020-06-0" + str(d), "signed_by_cm_superintendent": True, "signed_by_owner_rep": True}
                             for n, d in ((441, 5), (442, 8), (443, 9))])],
          backup=["cause document", "subcontractor quotes with breakdowns", "signed T&M tags"]),
    [], "APPROVE", "Signed T&M tags; mentions of 'superintendent' and 'crane' are not charges.", tricky=True)

add(build("CP-0207", "Self-performed generator pad", "Architect direction", "Architect field order FO-07", "2020-06-15", "2020-06-18", "2020-07-01",
          "Architect's field order adds a concrete pad for the emergency generator. CM self-performs with its own crew and skid steer (daily logs attached).",
          "Drawing E-001 shows the generator on grade with no pad.",
          cm=[labor("Concrete laborer", 32, 41.0), labor("Concrete finisher", 16, 52.0), equip("Skid steer (CM-owned)", 10, 96.0),
              line("material", "Ready-mix concrete 6 cy and rebar", 1840.0)],
          backup=["cause document", "labor timesheets", "equipment daily logs", "material invoices"]),
    [], "APPROVE", "Labor carries the 32% burden; owned equipment at 75% of Blue Book for logged hours.")

add(build("CP-0208", "Added fire sprinkler heads at stage", "ASI", "ASI-022", "2020-07-06", "2020-07-10", "2020-07-22",
          "ASI-022 adds sprinkler heads at the stage rigging. Includes the fire marshal permit revision fee, bond and insurance, and B&O tax, all without Fee.",
          "Drawing FP-102 shows no heads above the stage rigging.",
          subs=[sub("Sentinel Fire Protection", "Fire sprinklers", [("Sprinkler head and drop", 18, "ea", 210.0), ("Sprinkler fitter", 24, "hr", 98.0)])],
          cm=[line("permit", "Fire marshal permit revision fee", 640.0), line("bond_insurance", "Bond and insurance premium at actual cost", 112.0),
              line("bo_tax", "Washington B&O tax at actual cost", 41.0)]),
    [], "APPROVE", "Permit, bond, and B&O tax are included at cost with no Fee, as 6.5.3 requires.", tricky=True)

# ---------------------------------------------------------------- single violations (15)
add(build("CP-0209", "Added floor drains, kitchen", "RFI response", "RFI-140", "2020-07-13", "2020-07-16", "2020-07-30",
          "RFI-140 adds three floor drains in the kitchen. Plumbing sub price includes 15% overhead and profit.",
          "Drawing P-301 shows two floor drains in the kitchen.",
          subs=[sub("Cascade Plumbing", "Plumbing", [("Floor drain with trap primer", 3, "ea", 780.0), ("Plumber", 26, "hr", 92.0), ("Saw-cut and patch slab", 1, "ls", 1450.0)], own_pct=0.15)]),
    [("SUB_MARKUP", "Sub took 15% on its own work; 6.5.2 allows 10%.")], "RETURN", "Sub markup over the 10% limit.")

add(build("CP-0210", "Classroom smartboard backing and power", "Owner direction", "Owner email 2020-07-20", "2020-07-20", "2020-07-23", "2020-08-05",
          "Owner directed blocking and power for 16 smartboards. Electrical sub marked up its lower-tier blocking contractor at 10%.",
          "Drawings show whiteboards only; no smartboards.",
          subs=[sub("Sound Electric", "Electrical", [("Electrician", 48, "hr", 96.0), ("Receptacle and box", 16, "ea", 62.0)],
                    lower=[("Ridgeline Carpentry", "In-wall blocking at 16 locations", 5600.0)], lower_pct=0.10)]),
    [("SUB_MARKUP", "Sub took 10% on lower-tier work; 6.5.2 allows 5%.")], "RETURN", "Lower-tier markup over 5%.")

add(build("CP-0211", "Added exterior lighting at parking", "Owner direction", "Owner email 2020-08-03", "2020-08-03", "2020-08-06", "2020-08-19",
          "Owner added four pole lights at the staff lot. Cover sheet applies the 5% Fee to everything, including bond, insurance, and B&O tax.",
          "Drawing E-100 shows no lighting at the staff lot.",
          subs=[sub("Sound Electric", "Electrical", [("Pole light, base, and wiring", 4, "ea", 3650.0), ("Electrician", 40, "hr", 96.0)])],
          cm=[line("bond_insurance", "Bond and insurance premium", 260.0), line("bo_tax", "Washington B&O tax", 96.0)],
          fee_on=("direct", "subs", "bond_insurance", "bo_tax")),
    [("FEE_ON_EXCLUDED", "Fee applied to bond, insurance, and B&O tax; 6.5.3 excludes them.")], "RETURN", "Fee on excluded items.")

add(build("CP-0212", "Extra haul-off for abatement debris", "Concealed condition", "Field report FR-33 (asbestos mastic found)", "2020-08-10", "2020-08-10", "2020-08-24",
          "Asbestos mastic found under classroom flooring. Abatement sub price is fine; CM added dumpsters and haul-off and put the 5% Fee on them.",
          "Hazardous materials survey did not identify mastic in classrooms 110 to 116.",
          subs=[sub("Clearwater Abatement", "Abatement", [("Mastic abatement", 2400, "sf", 6.5), ("Air monitoring", 1, "ls", 1800.0)])],
          cm=[line("nss", "Additional dumpsters and haul-off (NSS)", 4200.0)],
          fee_on=("direct", "subs", "nss")),
    [("FEE_ON_EXCLUDED", "Fee applied to NSS haul-off; 5.3 and 6.5.3 say no Fee on NSS."),
     ("CONCEALED_CONDITION", "Concealed condition; owner's PM should review before approval.")], "ESCALATE",
    "Webster-type finding: Fee on NSS. Concealed condition also needs a person's review.")

add(build("CP-0213", "Add gym wall padding", "Owner direction", "Owner email 2020-08-17", "2020-08-17", "2020-08-20", "2020-09-02",
          "Owner added wall padding on two gym walls. Cover sheet Fee is 7.5%.",
          "Spec 11 66 23 includes padding on the north wall only.",
          subs=[sub("Summit Athletic Interiors", "Athletic equipment", [("Wall pad panels", 420, "sf", 18.5), ("Installer", 18, "hr", 70.0)])],
          fee_rate=0.075),
    [("FEE_RATE", "Fee at 7.5%; 6.5.3 sets 5%.")], "RETURN", "Fee rate above contract.")

add(build("CP-0214", "Revised casework per ASI-031", "ASI", "ASI-031", "2020-09-08", "2020-09-11", "2020-09-25",
          "ASI-031 revises science room casework. CP includes Project Manager time to price the change and estimating time.",
          "Drawing A-601 shows standard-height casework in rooms 201 and 203.",
          subs=[sub("Timberline Casework", "Casework", [("Revised base cabinets", 14, "lf", 410.0), ("Installer", 20, "hr", 76.0)])],
          cm=[labor("Project Manager, pricing this CP", 16, 68.0), labor("Estimator, quantity takeoff", 12, 60.0)]),
    [("COVERED_COST", "PM and estimating time to price a CP are covered by Fee/SGC under 5.5.")], "RETURN", "Costs covered by the Fee.")

add(build("CP-0215", "Stair nosing replacement per RFI-152", "RFI response", "RFI-152", "2020-09-14", "2020-09-17", "2020-10-01",
          "RFI-152 changes stair nosings at both stairs. Field supervision was provided by D. Alvarez, the CM's superintendent on this project.",
          "Spec 09 65 13 calls for rubber nosings; RFI-152 changes them to aluminum abrasive nosings.",
          subs=[sub("Evergreen Flooring", "Flooring", [("Aluminum abrasive nosing", 180, "lf", 24.0), ("Installer", 22, "hr", 70.0)])],
          cm=[labor("Field supervision", 24, 64.0, who="D. Alvarez")]),
    [("COVERED_COST", "Superintendent time is in SGC (Exhibit C) and covered under 5.5, even when labeled 'field supervision'.")], "RETURN",
    "Covered cost described without the word 'superintendent' on the line.", tricky=True)

add(build("CP-0216", "Bleacher anchor revisions", "RFI response", "RFI-158", "2020-09-21", "2020-09-24", "2020-10-07",
          "RFI-158 revises bleacher anchors. CM charged one of its project pickup trucks for material runs.",
          "Drawing S-310 shows wedge anchors; RFI-158 requires epoxy anchors.",
          subs=[sub("Summit Athletic Interiors", "Athletic equipment", [("Epoxy anchor upcharge", 96, "ea", 22.0), ("Installer", 14, "hr", 70.0)])],
          cm=[equip("Project pickup truck (CM-owned)", 12, 28.0)]),
    [("EQUIPMENT", "Project pickup trucks are included in SGC per Exhibit B; not chargeable to a CP.")], "RETURN", "Equipment that SGC already covers.")

add(build("CP-0217", "Storm line reroute at playfield", "Concealed condition", "Field report FR-41 (abandoned vault)", "2020-10-05", "2020-10-05", "2020-10-19",
          "An abandoned concrete vault blocked the storm line. CM excavated around it with its own excavator, charged at the full Blue Book rate.",
          "Civil drawings C-201 show no structures along the storm line route.",
          cm=[labor("Operator", 18, 58.0), labor("Laborer", 18, 41.0), equip("Excavator (CM-owned)", 18, 145.0, pct=1.0),
              line("material", "Pipe, bedding, and fittings", 2650.0)],
          backup=["cause document", "labor timesheets", "equipment daily logs", "material invoices"]),
    [("EQUIPMENT", "CM-owned equipment must be charged at 75% of Blue Book (6.5.4); charged at 100%."),
     ("CONCEALED_CONDITION", "Concealed condition; owner's PM should review before approval.")], "ESCALATE",
    "Owned-equipment rate over 75% of Blue Book; concealed condition needs review.")

add(build("CP-0218", "Rooftop unit curb adapters per RFI-166", "RFI response", "RFI-166", "2020-10-12", "2020-10-15", "2020-10-28",
          "RFI-166 adds curb adapters for two rooftop units. CP includes 6 hours of mobile hoisting to lift the adapters.",
          "Drawing M-501 shows units set on existing curbs.",
          subs=[sub("Rainier Mechanical", "HVAC", [("Curb adapter", 2, "ea", 2350.0), ("Sheet metal worker", 16, "hr", 94.0)])],
          cm=[rented("Mobile hoisting, 6 hours", 2280.0)]),
    [("EQUIPMENT", "Hoisting and crane is a Negotiated Support Service (Exhibit C), already paid as a lump sum.")], "RETURN",
    "Hoisting charged separately although it is NSS.", tricky=True)

add(build("CP-0219", "Added classroom sinks per ASI-036", "ASI", "ASI-036", "2020-10-19", "2020-10-22", "2020-11-04",
          "ASI-036 adds sinks in two classrooms. CM self-performed blocking with a 45% labor burden.",
          "Drawing P-210 shows no sinks in classrooms 105 and 107.",
          subs=[sub("Cascade Plumbing", "Plumbing", [("Sink, faucet, and trap", 2, "ea", 1120.0), ("Plumber", 20, "hr", 92.0)])],
          cm=[labor("Carpenter, in-wall blocking", 12, 50.0, burden=0.45)]),
    [("LABOR_BURDEN", "Labor burden 45%; Section 5.4 fixes it at 32%.")], "RETURN", "Wrong labor burden.")

add(build("CP-0220", "Window film at south classrooms", "Owner direction", "Owner email 2020-11-02", "2020-11-02", "2020-11-05", "2020-11-18",
          "Owner added solar film at south classrooms. Cover sheet total is higher than the sum of its lines.",
          "Spec 08 80 00 has clear glazing with no film.",
          subs=[sub("Clearview Glazing", "Glazing", [("Solar control film", 1350, "sf", 7.25), ("Installer", 24, "hr", 72.0)])],
          cover_adjust=1800.0),
    [("TIEOUT", "Cover sheet total is $1,800 more than its lines add up to.")], "RETURN", "Cover sheet does not tie out.")

add(build("CP-0221", "Corridor outlet additions, T&M", "Owner direction", "Owner email 2020-11-09", "2020-11-09", "2020-11-12", "2020-11-25",
          "Owner asked for added corridor outlets, done on T&M. Two of three tags lack the Owner's Representative's signature.",
          "Drawing E-201 shows outlets at 40-foot spacing in corridors.",
          subs=[sub("Sound Electric", "Electrical", [("Electrician", 28, "hr", 96.0), ("Duplex receptacle and box", 12, "ea", 58.0)],
                    tm_tags=[{"tag": "TM-512", "date": "2020-11-10", "signed_by_cm_superintendent": True, "signed_by_owner_rep": True},
                             {"tag": "TM-513", "date": "2020-11-11", "signed_by_cm_superintendent": True, "signed_by_owner_rep": False},
                             {"tag": "TM-514", "date": "2020-11-13", "signed_by_cm_superintendent": True, "signed_by_owner_rep": False}])],
          backup=["cause document", "subcontractor quotes with breakdowns", "T&M tags"]),
    [("MISSING_BACKUP", "Two T&M tags lack the Owner's Representative signature; 6.5.7 says unsigned tags are not accepted.")], "RETURN",
    "Unsigned T&M tags.")

add(build("CP-0222", "Revised fire alarm devices per RFI-171", "RFI response", "RFI-171", "2020-03-02", "2020-03-16", "2020-03-27",
          "RFI-171 response adds fire alarm strobes. CM gave notice on March 16; costs in the CP run from March 4.",
          "Drawing FA-101 shows horn-only devices in classrooms.",
          subs=[sub("Sentinel Fire Alarm", "Fire alarm", [("Horn/strobe device upgrade", 26, "ea", 145.0), ("Technician", 30, "hr", 98.0)])],
          costs_from="2020-03-04"),
    [("LATE_NOTICE", "Notice due 2020-03-09 under 6.2(a); given 2020-03-16. Costs before notice are waived.")], "RETURN", "Late notice.")

add(build("CP-0223", "Door closers at corridor doors per RFI-175", "RFI response", "RFI-175", "2020-03-23", "2020-03-26", "2020-04-08",
          "CM priced door closers for corridor doors C201 to C212 after RFI-175 confirmed closers are required.",
          "Spec 08 71 00, hardware set HW-4 (used at C201 to C212), already includes a surface closer on each door. RFI-175 response: 'Closers are required per HW-4.'",
          subs=[sub("Northwest Door & Hardware", "Doors and hardware", [("Surface closer", 12, "ea", 285.0), ("Door installer", 12, "hr", 78.0)])]),
    [("NOT_A_CHANGE", "Closers are already in hardware set HW-4; the RFI response confirms the base scope.")], "RETURN",
    "Work already in the Contract Documents.", tricky=True)

# ---------------------------------------------------------------- escalations (3)
add(build("CP-0224", "Permit delay, 12 days", "Other event", "City permit issued late (owner-held permit)", "2020-01-06", "2020-01-14", "2020-02-03",
          "The building permit, which the Owner was responsible for obtaining, was issued 12 days late. CM claims 12 days of extended SGC at the contract daily rate, with no Fee.",
          "Baseline schedule shows mobilization on 2020-01-06 as a critical path activity.",
          time_days=12, backup=["notice letter", "baseline schedule excerpt", "permit issuance record"]),
    [("TIME_IMPACT", "Delay claim; critical path and cause need a person's judgment (6.5.6, 3.4).")], "ESCALATE",
    "Priced correctly, but a delay claim needs the owner's PM to judge the critical path.")

add(build("CP-0225", "Unsuitable soils at gym footing", "Concealed condition", "Field report FR-12 (soft soils)", "2020-02-03", "2020-02-03", "2020-02-17",
          "Soft organic soils found at gym footing F-12 before excavation continued. Over-excavate and replace with structural fill per geotech.",
          "Geotechnical report assumed medium-dense sand at footing depth.",
          subs=[sub("Granite Earthworks", "Earthwork", [("Over-excavation", 140, "cy", 38.0), ("Structural fill, placed and compacted", 140, "cy", 62.0), ("Geotech testing", 1, "ls", 1650.0)])]),
    [("CONCEALED_CONDITION", "Differing site condition; owner's PM should confirm the condition and quantities.")], "ESCALATE",
    "Correctly priced, but site conditions need a person's review.")

add(build("CP-0226", "Seismic bracing upgrade per ASI-040", "ASI", "ASI-040", "2020-04-13", "2020-04-16", "2020-05-08",
          "ASI-040 adds seismic bracing to mechanical and electrical systems across the building after a code review.",
          "Drawings show bracing only at rooftop equipment.",
          subs=[sub("Rainier Mechanical", "HVAC", [("Seismic bracing, ductwork and piping", 1, "ls", 168000.0), ("Engineering and submittals", 1, "ls", 12500.0)]),
                sub("Sound Electric", "Electrical", [("Seismic bracing, conduit and equipment", 1, "ls", 88000.0)])]),
    [("OVER_AUTHORITY", "Total exceeds $250,000; Board approval required per Exhibit D.")], "ESCALATE",
    "Above the Owner's Representative's approval limit.")

# ---------------------------------------------------------------- mixed, Webster-like (4)
add(build("CP-0227", "Weather-related delay with extended conditions", "Other event", "Notice letter NL-09", "2020-11-16", "2020-11-24", "2020-12-08",
          "CM claims 6 days of extended general conditions for a roofing delay and applies the 5% Fee to the extended SGC.",
          "Schedule shows roofing on the critical path in November.",
          time_days=6, fee_on=("direct", "subs", "time"), backup=["notice letter", "schedule excerpt", "weather records"]),
    [("TIME_IMPACT", "Delay claim needs critical-path and cause review."),
     ("FEE_ON_EXCLUDED", "Fee applied to the SGC time extension; 5.2 and 6.5.6 say no Fee.")], "ESCALATE",
    "Fee on SGC plus a delay claim.")

add(build("CP-0228", "Kitchen hood relocation per RFI-180", "RFI response", "RFI-180", "2020-04-20", "2020-04-23", "2020-05-06",
          "RFI-180 moves the kitchen hood. CP charges NSS dumpsters with Fee, a CM-owned forklift at full Blue Book, and Project Engineer coordination hours.",
          "Drawing M-401 shows the hood on the east wall.",
          subs=[sub("Rainier Mechanical", "HVAC", [("Relocate hood and duct", 1, "ls", 9400.0), ("Sheet metal worker", 32, "hr", 94.0)])],
          cm=[line("nss", "Dumpster and haul-off (NSS)", 1450.0), equip("Forklift (CM-owned)", 10, 72.0, pct=1.0),
              labor("Project Engineer coordination", 14, 55.0)],
          fee_on=("direct", "subs", "nss")),
    [("FEE_ON_EXCLUDED", "Fee on NSS haul-off."), ("EQUIPMENT", "Owned forklift at 100% of Blue Book; limit is 75%."),
     ("COVERED_COST", "Project Engineer is an SGC position (Exhibit C); covered under 5.5.")], "RETURN",
    "Three Webster-type findings in one CP.")

add(build("CP-0229", "Added restroom partitions per ASI-044", "ASI", "ASI-044", "2020-05-18", "2020-06-01", "2020-06-12",
          "ASI-044 adds two toilet partitions. Notice given June 1; partition sub took 12% overhead and profit.",
          "Drawing A-120 shows six partitions in restroom 140.",
          subs=[sub("Pacific Specialties", "Toilet partitions", [("Phenolic partition and hardware", 2, "ea", 1480.0), ("Installer", 8, "hr", 70.0)], own_pct=0.12)],
          costs_from="2020-05-20"),
    [("SUB_MARKUP", "Sub took 12% on its own work; limit is 10%."),
     ("LATE_NOTICE", "Notice due 2020-05-26 (Memorial Day roll-forward); given 2020-06-01.")], "RETURN",
    "Two violations; the notice date rolls past Memorial Day.", tricky=True)

add(build("CP-0230", "Gym sound panels per Owner direction", "Owner direction", "Owner email 2020-06-08", "2020-06-08", "2020-06-11", "2020-06-24",
          "Owner added acoustic panels in the gym. Acoustics sub sent a lump-sum quote without a breakdown; cover sheet total also runs $950 high.",
          "Spec 09 84 00 has no acoustic panels in the gym.",
          subs=[sub("Harmony Acoustics", "Acoustic treatments", [("Acoustic wall panels", 640, "sf", 21.0), ("Installer", 30, "hr", 70.0)], breakdown=False)],
          cover_adjust=950.0, backup=["cause document", "subcontractor lump-sum quote"]),
    [("MISSING_BACKUP", "Sub quote has no breakdown; 6.3 and Exhibit E require one."), ("TIEOUT", "Cover sheet is $950 more than its lines.")], "RETURN",
    "Missing breakdown and a tie-out error.")

# ---------------------------------------------------------------- messy: quotes arrive as email text (6)
add(build("CP-0231", "Science room gas shutoffs per RFI-183", "RFI response", "RFI-183", "2020-06-22", "2020-06-25", "2020-07-08",
          "RFI-183 adds emergency gas shutoff valves in two science rooms. Plumbing sub sent pricing by email.",
          "Drawing P-220 shows gas outlets at lab benches with no room shutoff.",
          subs=[as_email(sub("Cascade Plumbing", "Plumbing", [("Emergency gas shutoff valve with button", 2, "ea", 1385.0), ("Gas piping and fittings", 1, "ls", 940.0), ("Plumber", 18, "hr", 92.0)], own_pct=0.15),
                         "Per RFI-183, here is our price for the two gas shutoffs:")],
          backup=["cause document", "subcontractor email quote"]),
    [("SUB_MARKUP", "Email quote shows 15% OH&P on own work; limit is 10%.")], "RETURN", "Markup over limit, stated only in email text.", tricky=True)

add(build("CP-0232", "Locker room bench relocation", "Owner direction", "Owner email 2020-06-29", "2020-06-29", "2020-07-01", "2020-07-14",
          "Owner moved the locker room benches. Includes 10 hours of coordination by J. Park, who manages this project for the CM day to day.",
          "Drawing A-140 shows benches along the north wall.",
          subs=[sub("Summit Athletic Interiors", "Athletic equipment", [("Remove and reinstall benches", 6, "ea", 240.0), ("Installer", 10, "hr", 70.0)])],
          cm=[labor("Coordination time, J. Park", 10, 68.0)]),
    [("COVERED_COST", "J. Park is the CM's project manager; that position is in SGC (Exhibit C) and covered under 5.5.")], "RETURN",
    "Covered cost with no job title on the line.", tricky=True)

add(build("CP-0233", "Additional whiteboards per ASI-047", "ASI", "ASI-047", "2020-07-06", "2020-07-09", "2020-07-22",
          "ASI-047 adds whiteboards in four rooms. Specialties sub sent an email quote; the price includes their pickup of the boards from the supplier's yard.",
          "Drawing A-301 shows tackboards only in rooms 210 to 213.",
          subs=[as_email(sub("Pacific Specialties", "Specialties", [("Whiteboard 4x12, installed", 4, "ea", 690.0), ("Pickup and delivery from supplier", 1, "ls", 180.0), ("Installer", 8, "hr", 70.0)]),
                         "Pricing for ASI-047 whiteboards below. We'll handle pickup at the supplier.")],
          backup=["cause document", "subcontractor email quote"]),
    [], "APPROVE", "Clean; 'pickup' is the sub's material delivery, not a CM project truck.", tricky=True)

add(build("CP-0234", "Ceiling fans in gym per Owner direction", "Owner direction", "Owner email 2020-07-13", "2020-07-13", "2020-07-16", "2020-07-29",
          "Owner added high-volume fans in the gym. Electrical sub sent an email quote that includes its structural lower-tier.",
          "Drawing E-301 shows no fans in the gym.",
          subs=[as_email(sub("Sound Electric", "Electrical", [("HVLS fan wiring and controls", 3, "ea", 1650.0), ("Electrician", 30, "hr", 96.0)],
                             lower=[("Ironwood Structural", "Fan mounting steel at 3 locations", 9800.0)], lower_pct=0.08),
                         "Quote for the three gym fans, including Ironwood's mounting steel:")],
          backup=["cause document", "subcontractor email quote"]),
    [("SUB_MARKUP", "8% on lower-tier work in the email quote; 6.5.2 allows 5%.")], "RETURN", "Lower-tier markup over 5%, in email text.", tricky=True)

add(build("CP-0235", "Patch and paint after abatement", "ASI", "ASI-050", "2020-07-20", "2020-07-23", "2020-08-05",
          "ASI-050 adds patching and painting of walls opened during abatement. Painting sub emailed its price.",
          "Spec 09 91 23 covers painting of new walls only.",
          subs=[as_email(sub("Brightline Painting", "Painting", [("Patch and paint walls", 2800, "sf", 2.15), ("Painter", 24, "hr", 66.0)]),
                         "Here is our patch and paint number for ASI-050.")],
          backup=["cause document", "subcontractor email quote"]),
    [], "APPROVE", "Clean email quote at 10% OH&P.")

add(build("CP-0236", "Added hose bibbs, T&M", "Owner direction", "Owner email 2020-07-27", "2020-07-27", "2020-07-29", "2020-08-11",
          "Owner asked for four added hose bibbs at the courtyard, done on T&M. Sub's email says the tags were signed by its own foreman.",
          "Drawing P-102 shows two hose bibbs at the courtyard.",
          subs=[as_email(sub("Cascade Plumbing", "Plumbing", [("Hose bibb and piping", 4, "ea", 310.0), ("Plumber", 16, "hr", 92.0)]),
                         "T&M summary for the courtyard hose bibbs (tags TM-601 to TM-603):",
                         extra="Tags were signed by our foreman, Luis, each day.")],
          backup=["cause document", "subcontractor email quote", "T&M tags"]),
    [("MISSING_BACKUP", "T&M tags signed only by the sub's foreman; 6.5.7 needs the CM superintendent and Owner's Representative.")], "RETURN",
    "Unacceptable T&M tags, described only in text.", tricky=True)



def main():
    assert len(CASES) == 36, len(CASES)
    public, key = [], []
    for pkg, flags, route, why, tricky in CASES:
        rule = pkg.pop("_rule")
        due = notice_due(pkg["cause"]["event_date"], rule)
        late = pkg["notice_date"] > due
        has_late = any(f["type"] == "LATE_NOTICE" for f in flags)
        assert late == has_late, (pkg["id"], due, pkg["notice_date"])          # labels match the date code
        over = pkg["cover_sheet"]["total_requested"] > 250000
        assert over == any(f["type"] == "OVER_AUTHORITY" for f in flags), pkg["id"]
        if any(f["type"] in ESCALATION_TYPES for f in flags):
            assert route == "ESCALATE", pkg["id"]
        public.append(pkg)
        key.append({"id": pkg["id"], "expected_flags": flags, "expected_route": route, "notice_rule": rule,
                    "notice_due": due, "why": why, "tricky": tricky})
    meta = {"contract": "../demo1/data/synthetic_contract.md", "generated_by": "data/build_cases.py",
            "calendar": "Washington State legal holidays, 2020 (Demo 2 deadlines.py)"}
    (ROOT / "data" / "cases.json").write_text(json.dumps({"meta": meta, "cases": public}, indent=2), encoding="utf-8")
    (ROOT / "data" / "answer_key.json").write_text(json.dumps({"meta": meta, "cases": key}, indent=2), encoding="utf-8")
    n_flags = sum(len(k["expected_flags"]) for k in key)
    from collections import Counter
    print(f"{len(key)} CPs, {n_flags} seeded issues; routes {dict(Counter(k['expected_route'] for k in key))}; "
          f"tricky {sum(k['tricky'] for k in key)}")


if __name__ == "__main__":
    main()
