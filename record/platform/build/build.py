#!/usr/bin/env python3
"""Build the synthetic platform sample data under record/platform/.

Standard library only. Run from anywhere:

    python3 record/platform/build/build.py

It reads only data files (record/bundle.json, demo1/data/synthetic_contract.md,
demo3/data/cases.json, demo4/data/cases.json, demo4/data/schedule.json),
writes every output under record/platform/, and stops with an AssertionError
on any failed check. Everything it writes is synthetic and was written with
AI assistance for INFO 492 C coursework.
"""
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAT = ROOT / "record" / "platform"
DOCS = PLAT / "docs"
BUILT = "2026-11-17"

PRIME_NOTICE_DAYS = 7          # contract A § 6.2(a)-(c)
PRIME_NOTICE_OTHER_DAYS = 14   # contract A § 6.2(d)
PRIME_CP_DAYS = 21             # contract A § 6.3, after notice
PRIME_PR_DAYS = 14             # contract A § 6.3, after a Proposal Request
CONTRACT_DAYS = 540            # contract A § 3.2
STATED_RATE = 3185             # contract A § 5.2


def rel(p):
    return str(Path(p).relative_to(ROOT))


def load_json(p):
    with open(ROOT / p, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text if text.endswith("\n") else text + "\n")


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("&", " ")).strip("-")


def money(x):
    return round(float(x) + 0.0, 2)


def long_date(s):
    d = dt.date.fromisoformat(s)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------
BUNDLE = load_json("record/bundle.json")
CONTRACT_A_TEXT = (ROOT / "demo1/data/synthetic_contract.md").read_text(encoding="utf-8")
CASES3 = load_json("demo3/data/cases.json")["cases"]
CASES4 = load_json("demo4/data/cases.json")["cases"]
CASES = {c["id"]: c for c in CASES3 + CASES4}
SCHED_U1 = load_json("demo4/data/schedule.json")

CONTRACT_DOC = [d for d in BUNDLE["documents"] if d["kind"] == "contract"]
assert len(CONTRACT_DOC) == 1, "expected one contract document in the bundle"
CONTRACT_DOC = CONTRACT_DOC[0]
CONTRACT_A_PIECES = "\n".join(p["body"] for p in CONTRACT_DOC["pieces"])
BUNDLE_TEXT = json.dumps(BUNDLE)

# The bundle names the GC/CM and the Architect; use them rather than invent.
GC_NAME = "Example Builders, Inc."
ARCH_NAME = "Example Architecture, PLLC"
OWNER_NAME = BUNDLE["project"]["owner_org"]
for nm in (GC_NAME, ARCH_NAME, OWNER_NAME):
    assert nm in BUNDLE_TEXT, nm

# --------------------------------------------------------------------------
# Subcontractor firms (from the cases' subcontractor_quotes)
# --------------------------------------------------------------------------
TRADE_FIX = {"Pacific Specialties": "Specialties"}
firm_order, firm_trade = [], {}
lower_tier_seen = []  # (firm, parent firm, change)
for c in CASES3 + CASES4:
    for q in c["subcontractor_quotes"]:
        f = q["firm"]
        if f not in firm_trade:
            firm_order.append(f)
            firm_trade[f] = TRADE_FIX.get(f, q["trade"])
        for lt in q.get("lower_tier") or []:
            lower_tier_seen.append((lt["firm"], f, c["id"]))
# CP-0234's quote is an email; its lower tier is named only in the text.
assert "Ironwood Structural" in CASES["CP-0234"]["subcontractor_quotes"][0]["text"]
lower_tier_seen.append(("Ironwood Structural", "Sound Electric", "CP-0234"))
# The flatwork sub on CP-0410 is unnamed in the case but named in the bundle.
assert "Cornerstone Flatwork" in BUNDLE_TEXT
firm_order.append("Cornerstone Flatwork")
firm_trade["Cornerstone Flatwork"] = "Site concrete flatwork"

# Subcontract parameters. tmpl: A (§), B (Section), C (¶).
# flow: "yes" (prime notice terms flow down), "no" (they do not), "override"
# (general flow-down clause, but a "notwithstanding" sentence makes the sub's
# own longer notice window govern).
SUBS = {
    "Clearwater Abatement":      dict(tmpl="A", notice=3,  unit="calendar", flow="yes", mo=10, ml=5,  price=7,  pif=True,  delay="pass", amount=540000,  date="2019-12-02"),
    "Granite Earthworks":        dict(tmpl="B", notice=14, unit="calendar", flow="no",  mo=10, ml=5,  price=10, pif=True,  delay="none", amount=920000, date="2019-12-09"),
    "Cornerstone Flatwork":      dict(tmpl="C", notice=5,  unit="calendar", flow="yes", mo=10, ml=5,  price=7,  pif=True,  delay="pass", amount=385000,  date="2020-01-20"),
    "Evergreen Site Works":      dict(tmpl="A", notice=4,  unit="calendar", flow="yes", mo=10, ml=5,  price=10, pif=True,  delay="pass", amount=610000,  date="2020-01-20"),
    "Granite Concrete":          dict(tmpl="B", notice=3,  unit="calendar", flow="yes", mo=10, ml=5,  price=7,  pif=False, delay="gc",   amount=1320000, date="2019-12-16"),
    "Puget Steel Erectors":      dict(tmpl="C", notice=10, unit="business", flow="no",  mo=10, ml=5,  price=10, pif=True,  delay="none", amount=1450000, date="2019-11-18"),
    "Olympic Structural":        dict(tmpl="A", notice=5,  unit="calendar", flow="yes", mo=10, ml=5,  price=7,  pif=True,  delay="pass", amount=480000,  date="2020-03-09"),
    "Summit Roofing":            dict(tmpl="A", notice=10, unit="calendar", flow="override", mo=10, ml=5, price=10, pif=True, delay="pass", amount=1010000, date="2020-01-13"),
    "Cascade Glazing":           dict(tmpl="B", notice=4,  unit="calendar", flow="yes", mo=10, ml=5,  price=10, pif=True,  delay="pass", amount=820000,  date="2019-12-16"),
    "Clearview Glazing":         dict(tmpl="C", notice=5,  unit="calendar", flow="yes", mo=8,  ml=5,  price=7,  pif=True,  delay="none", amount=185000,  date="2020-02-24"),
    "Evergreen Framing":         dict(tmpl="A", notice=3,  unit="calendar", flow="yes", mo=10, ml=5,  price=7,  pif=False, delay="gc",   amount=1820000, date="2019-12-02"),
    "Brightline Painting":       dict(tmpl="B", notice=5,  unit="calendar", flow="yes", mo=10, ml=5,  price=7,  pif=True,  delay="pass", amount=520000,  date="2020-01-06"),
    "Northwest Floors":          dict(tmpl="C", notice=4,  unit="calendar", flow="yes", mo=10, ml=5,  price=10, pif=True,  delay="pass", amount=560000,  date="2020-01-06"),
    "Evergreen Flooring":        dict(tmpl="A", notice=5,  unit="calendar", flow="yes", mo=10, ml=5,  price=7,  pif=True,  delay="none", amount=410000,  date="2020-01-06"),
    "Timberline Casework":       dict(tmpl="B", notice=4,  unit="calendar", flow="yes", mo=10, ml=5,  price=10, pif=True,  delay="pass", amount=470000,  date="2020-01-13"),
    "Northwest Door & Hardware": dict(tmpl="C", notice=3,  unit="calendar", flow="yes", mo=10, ml=5,  price=7,  pif=True,  delay="pass", amount=430000,  date="2019-12-23"),
    "Pacific Specialties":       dict(tmpl="A", notice=5,  unit="calendar", flow="yes", mo=12, ml=5,  price=7,  pif=True,  delay="pass", amount=210000,  date="2020-01-27"),
    "Harmony Acoustics":         dict(tmpl="B", notice=21, unit="calendar", flow="no",  mo=10, ml=5,  price=14, pif=True,  delay="none", amount=240000,  date="2020-01-27"),
    "Summit Athletic Interiors": dict(tmpl="C", notice=5,  unit="calendar", flow="yes", mo=10, ml=5,  price=10, pif=True,  delay="pass", amount=365000,  date="2020-01-27"),
    "Cascade Plumbing":          dict(tmpl="A", notice=3,  unit="calendar", flow="yes", mo=10, ml=5,  price=7,  pif=True,  delay="pass", amount=1150000, date="2019-11-25"),
    "Rainier Mechanical":        dict(tmpl="B", notice=2,  unit="calendar", flow="yes", mo=10, ml=5,  price=21, pif=False, delay="gc",   amount=2050000, date="2019-11-25"),
    "Sound Electric":            dict(tmpl="C", notice=3,  unit="calendar", flow="yes", mo=10, ml=10, price=7,  pif=False, delay="gc",   amount=1780000, date="2019-11-25"),
    "Sentinel Fire Protection":  dict(tmpl="A", notice=4,  unit="calendar", flow="yes", mo=10, ml=5,  price=7,  pif=True,  delay="pass", amount=430000,  date="2019-12-09"),
    "Sentinel Fire Alarm":       dict(tmpl="B", notice=4,  unit="calendar", flow="yes", mo=10, ml=5,  price=7,  pif=True,  delay="pass", amount=285000,  date="2019-12-09"),
    "Cascade Coatings":          dict(tmpl="C", notice=5,  unit="calendar", flow="yes", mo=10, ml=5,  price=7,  pif=True,  delay="pass", amount=145000,  date="2020-07-20"),
}
assert set(SUBS) == set(firm_order), set(SUBS) ^ set(firm_order)

SCOPE = {
    "Clearwater Abatement": "removal and disposal of asbestos-containing and other regulated materials in Wings A and B and the existing gym and commons, with clearance air testing coordination",
    "Granite Earthworks": "excavation, shoring, over-excavation and structural fill, grading and erosion control for the addition and site",
    "Cornerstone Flatwork": "site concrete curbs, sidewalks, flatwork and the concrete bands at the bus loop and fire lane",
    "Evergreen Site Works": "playground equipment, play surfacing, site furnishings, site fencing and gates",
    "Granite Concrete": "footings, foundation walls, slab on grade and elevated slab concrete for the addition, including reinforcing and finishing",
    "Puget Steel Erectors": "structural steel, joists and metal deck for the addition, including detailing, fabrication, delivery and erection",
    "Olympic Structural": "seismic upgrade steel for Wing B, including collectors, straps, drag struts and connections",
    "Summit Roofing": "roofing and sheet metal for the addition and the reroof of the existing building",
    "Cascade Glazing": "aluminum storefront, curtain wall and windows at the addition and replacement windows in the existing building",
    "Clearview Glazing": "glazing films, mirrors and interior glazing",
    "Evergreen Framing": "metal stud framing, gypsum board, blocking, access panels and soffits throughout",
    "Brightline Painting": "interior and exterior painting and wall coverings",
    "Northwest Floors": "resilient flooring, rubber tile and base in the addition classrooms and corridors",
    "Evergreen Flooring": "flooring, stair treads and nosings in the existing building",
    "Timberline Casework": "architectural casework and millwork, including science room casework",
    "Northwest Door & Hardware": "hollow metal and wood doors, frames and finish hardware",
    "Pacific Specialties": "toilet partitions, visual display boards and Division 10 specialties",
    "Harmony Acoustics": "acoustic wall and ceiling panels and sound treatments",
    "Summit Athletic Interiors": "gym equipment, wall padding, bleachers and locker room benches",
    "Cascade Plumbing": "plumbing, roof drainage, natural gas piping and plumbing fixtures",
    "Rainier Mechanical": "HVAC equipment, ductwork, piping, controls and seismic bracing of mechanical systems",
    "Sound Electric": "electrical service, power, lighting, low-voltage pathways and seismic bracing of electrical systems",
    "Sentinel Fire Protection": "fire sprinkler systems in the addition and existing building",
    "Sentinel Fire Alarm": "fire alarm and detection systems",
    "Cascade Coatings": "concrete moisture vapor mitigation coatings and floor preparation",
}
assert set(SCOPE) == set(SUBS)

ABBR = {f: "".join(w[0] for w in re.findall(r"[A-Za-z]+", f)).upper()[:4] for f in SUBS}
# make abbreviations unique
_seen = {}
for f in firm_order:
    a = ABBR[f]
    if a in _seen:
        a = (a + slug(f).replace("-", "")[-2:].upper())[:5]
    _seen[a] = f
    ABBR[f] = a
assert len(set(ABBR.values())) == len(ABBR)

NUM_PREFIX = {"A": "COR-", "B": "CR ", "C": "PCO-"}


def sub_key(firm):
    return "sub-" + slug(firm)


# --------------------------------------------------------------------------
# Subcontract templates
# --------------------------------------------------------------------------
FLOW_YES = {
    "A": "To the extent of the Subcontract Work, Subcontractor assumes toward Contractor all obligations that Contractor assumes toward Owner and Architect under the Prime Contract, including its notice, claim and change procedures.",
    "B": "The Prime Contract is incorporated by reference, and Subcontractor is bound to Contractor by its terms, including the notice and claim periods in Articles 6 and 10, as Contractor is bound to Owner.",
    "C": "Subcontractor is bound to Contractor by every term of the Prime Contract that applies to the Subcontract Work, including the notice and change provisions.",
}
FLOW_NO = {
    "A": "The Prime Contract is incorporated for scope and technical requirements only; its notice, claim and change procedures do not apply to this Subcontract.",
    "B": "The Prime Contract is listed for reference only, and its notice, claim and change periods do not apply to Subcontractor.",
    "C": "Prime Contract terms do not apply to Subcontractor except the Drawings and Specifications; the notice periods in this Subcontract are the only ones that apply.",
}
FLOW_OVERRIDE = "Notwithstanding § 2.1, the notice period in this § 4.2 governs over any notice period in the Prime Contract."
BOOL_MARKERS = {
    ("notice_flowdown", True): ["including its notice", "including the notice"],
    ("notice_flowdown", False): ["do not apply", "governs over any notice period"],
    ("pay_if_paid", True): ["is a condition precedent"],
    ("pay_if_paid", False): ["is not a condition precedent"],
}


def window(n, unit):
    return f"{n} business days" if unit == "business" else f"{n} days"


def notice_sentence(t, n, unit):
    w = window(n, unit)
    return {
        "A": f"Subcontractor shall give Contractor written notice of any event, direction or condition that Subcontractor believes changes its cost or time within {w} after Subcontractor first learns of it.",
        "B": f"Notice of any claim for added cost or time shall be given to Contractor in writing no later than {w} after the event giving rise to it.",
        "C": f"Subcontractor must notify Contractor in writing within {w} of any instruction, RFI response, submittal comment or site condition it believes is a change.",
    }[t]


def pricing_sentence(t, p):
    return {
        "A": f"Subcontractor shall submit a complete, itemized price for a change within {p} days after Contractor's written request.",
        "B": f"When Contractor requests a price for a change, Subcontractor shall deliver it within {p} days.",
        "C": f"Change pricing is due {p} days after Contractor asks for it.",
    }[t]


def markup_sentence(t, mo, ml):
    return {
        "A": f"On changed work, Subcontractor may add overhead and profit of up to {mo}% on its own direct cost and up to {ml}% on the cost of work by its lower-tier subcontractors.",
        "B": f"Overhead and profit on changes is limited to {mo}% of Subcontractor's own direct cost and {ml}% of lower-tier subcontract cost.",
        "C": f"Markup on changed work: {mo}% on Subcontractor's own costs, {ml}% on lower-tier costs, and nothing on markup.",
    }[t]


def pif_sentence(t, pif):
    if pif:
        return {
            "A": "Receipt of payment from Owner for the Subcontract Work is a condition precedent to Contractor's obligation to pay Subcontractor.",
            "B": "Contractor's receipt of payment from Owner is a condition precedent to any payment to Subcontractor for that Work.",
            "C": "Payment by Owner to Contractor is a condition precedent to payment to Subcontractor.",
        }[t]
    return {
        "A": "Contractor shall pay Subcontractor within 10 days after Contractor receives payment from Owner, and in any event within 45 days after Subcontractor's application; receipt of Owner payment is not a condition precedent to payment.",
        "B": "Payment to Subcontractor is due within 7 days after Contractor is paid for the Work, but receipt of Owner payment is not a condition precedent; if Owner has not paid within 60 days for reasons not caused by Subcontractor, Contractor shall pay.",
        "C": "Owner's payment to Contractor is not a condition precedent to payment to Subcontractor; Contractor shall pay within 30 days after a proper application.",
    }[t]


DELAY = {
    "pass": ("Contractor shall pay Subcontractor for delay only to the extent the Owner pays Contractor for that delay under the Prime Contract.",
             "only to the extent the Owner pays Contractor for that delay"),
    "none": ("Subcontractor's sole remedy for any delay, whatever its cause, is an extension of the Subcontract Time.",
             "sole remedy for any delay, whatever its cause, is an extension of the Subcontract Time"),
    "gc": ("Contractor shall pay Subcontractor's documented extended field costs for delay caused by Contractor or its other subcontractors, and shall pass through Owner-caused delay costs as Owner pays them.",
           "Contractor shall pay Subcontractor's documented extended field costs for delay caused by Contractor or its other subcontractors"),
}

SYN_NOTE = ("> **SYNTHETIC DOCUMENT.** A fictional subcontract written with AI assistance for INFO 492 C coursework. "
            "No real firm, person or project is represented.")


def header_block(firm, p):
    return "\n".join([
        f"**Contractor:** {GC_NAME} (\"Contractor\"), GC/CM for the Project",
        f"**Subcontractor:** {firm} (\"Subcontractor\")",
        f"**Project:** School Modernization and Addition, for {OWNER_NAME} (\"Owner\")",
        "**Prime Contract:** Agreement Between Owner and Construction Manager as Constructor (GC/CM) dated June 17, 2019 (the \"Prime Contract\")",
        f"**Architect:** {ARCH_NAME}",
        f"**Subcontract Sum:** ${p['amount']:,}",
        f"**Date:** {long_date(p['date'])}",
    ])


def render_subcontract(firm, p):
    """Return (markdown, terms). Every term sentence is placed verbatim."""
    t = p["tmpl"]
    trade = firm_trade[firm]
    s_notice = notice_sentence(t, p["notice"], p["unit"])
    s_price = pricing_sentence(t, p["price"])
    s_markup = markup_sentence(t, p["mo"], p["ml"])
    s_pif = pif_sentence(t, p["pif"])
    s_delay, v_delay = DELAY[p["delay"]]
    if p["flow"] == "yes":
        s_flow = FLOW_YES[t]
    elif p["flow"] == "no":
        s_flow = FLOW_NO[t]
    else:
        assert t == "A"
        s_flow = FLOW_YES[t]  # the general clause; the override sits in § 4.2
    flow_value = p["flow"] == "yes"

    if t == "A":
        c = {"flow": "§ 2.1", "notice": "§ 4.2", "price": "§ 4.3", "markup": "§ 4.4", "pif": "§ 5.2", "delay": "§ 3.2"}
        notice_para = s_notice + (" " + FLOW_OVERRIDE if p["flow"] == "override" else "")
        md = f"""# Subcontract Agreement: {trade}

{SYN_NOTE}

{header_block(firm, p)}

## Article 1. The Work

§ 1.1 Subcontractor shall perform the following work (the "Subcontract Work"): {SCOPE[firm]}.

§ 1.2 Subcontractor shall furnish all labor, materials, equipment and supervision for the Subcontract Work and shall coordinate with other trades as Contractor directs.

§ 1.3 The Subcontract Documents are this Agreement, the Prime Contract to the extent stated in Article 2, the Drawings and Specifications listed in Exhibit 1, and Modifications issued after the date of this Agreement.

## Article 2. Relationship to the Prime Contract

§ 2.1 {s_flow}

§ 2.2 Subcontractor shall not communicate directly with Owner or Architect about changes, claims or payment. All such communications go through Contractor.

## Article 3. Time

§ 3.1 Subcontractor shall perform the Subcontract Work in accordance with Contractor's project schedule as updated from time to time and shall supply crews sufficient to meet it.

§ 3.2 {s_delay}

§ 3.3 Subcontractor shall give Contractor a two-week look-ahead schedule each Monday.

## Article 4. Changes

§ 4.1 Contractor may order changes in the Subcontract Work by written change directive. No other person may authorize a change.

§ 4.2 {notice_para} The notice shall describe the event, the document or direction involved, and a preliminary estimate of cost and time. Subcontractor waives any adjustment for costs incurred before timely notice is given.

§ 4.3 {s_price} The price shall show labor hours and rates, materials, equipment, lower-tier quotes with their own breakdowns, and markup.

§ 4.4 {s_markup} No markup is allowed on markup.

§ 4.5 Time-and-material work requires tags signed each day by Contractor's superintendent. Unsigned tags are not accepted.

## Article 5. Payment

§ 5.1 Subcontractor shall submit a payment application by the 20th of each month for Work completed through that date, with conditional lien waivers for itself and its lower-tier subcontractors.

§ 5.2 {s_pif}

§ 5.3 Contractor shall retain 5% of each progress payment and release it when Owner releases retainage under the Prime Contract.

## Article 6. Insurance, Warranty and Disputes

§ 6.1 Subcontractor shall carry commercial general liability insurance of at least $1,000,000 per occurrence and $2,000,000 in the aggregate, naming Contractor and Owner as additional insureds.

§ 6.2 Subcontractor warrants the Subcontract Work for one year after Substantial Completion of the Project.

§ 6.3 Disputes that involve acts of Owner or Architect are resolved under the Prime Contract's dispute procedures. Other disputes go to mediation and then to the Superior Court of King County, Washington.

## Signatures

Contractor: {GC_NAME}, by its Project Manager

Subcontractor: {firm}, by an authorized officer
"""
    elif t == "B":
        c = {"flow": "Section 3.2", "notice": "Section 7.1", "price": "Section 6.2", "markup": "Section 6.3", "pif": "Section 5.2", "delay": "Section 8.1"}
        md = f"""# Short Form Subcontract ({trade})

{SYN_NOTE}

{header_block(firm, p)}

## Article 1. Agreement

Section 1.1 Contractor engages Subcontractor, and Subcontractor agrees, to perform the Subcontract Work for the Subcontract Sum, subject to additions and deductions by written change order.

## Article 2. Scope

Section 2.1 The Subcontract Work is {SCOPE[firm]}, complete and ready for use, including layout, protection of adjacent work, daily cleanup and removal of its own debris.

Section 2.2 Subcontractor has examined the site and the Drawings and Specifications and accepts the existing conditions shown on them.

## Article 3. Contract Documents

Section 3.1 This Subcontract consists of this form, Exhibit 1 (list of Drawings and Specifications), Exhibit 2 (schedule of values) and the Prime Contract to the extent stated in Section 3.2.

Section 3.2 {s_flow}

## Article 4. Schedule

Section 4.1 Subcontractor shall start within 5 working days after Contractor's notice to mobilize and shall keep pace with the project schedule.

## Article 5. Payment

Section 5.1 Applications are due on the 20th of each month on Contractor's form, with a schedule of values update and lien waivers.

Section 5.2 {s_pif}

Section 5.3 Retainage is 5% of each progress payment.

## Article 6. Changes

Section 6.1 Changes are made only by written change order or written directive signed by Contractor's Project Manager.

Section 6.2 {s_price} Late pricing may be determined by Contractor from its own estimate.

Section 6.3 {s_markup} Equipment owned by Subcontractor is charged at no more than 75% of the published rental rate.

## Article 7. Claims and Notice

Section 7.1 {s_notice} A notice must state the cause and give a preliminary estimate.

Section 7.2 Claims not noticed within that period are waived.

## Article 8. Delays

Section 8.1 {s_delay}

Section 8.2 Subcontractor shall provide added crews at its own cost if it falls behind for reasons within its control.

## Article 9. Insurance

Section 9.1 Commercial general liability of $1,000,000 per occurrence and $2,000,000 aggregate, automobile liability of $1,000,000, and Washington industrial insurance as required by law.

## Article 10. General

Section 10.1 Washington law governs this Subcontract. Venue is King County.

Section 10.2 Subcontractor may not assign this Subcontract or sublet the whole of the Subcontract Work without Contractor's written consent.

Signed for Contractor ({GC_NAME}) and for Subcontractor ({firm}).
"""
    else:
        c = {"flow": "¶ 3", "notice": "¶ 9", "price": "¶ 10", "markup": "¶ 11", "pif": "¶ 6", "delay": "¶ 13"}
        md = f"""# Trade Subcontract: {trade}

{SYN_NOTE}

{header_block(firm, p)}

¶ 1. **Work.** {SCOPE[firm][0].upper() + SCOPE[firm][1:]}, as shown and specified, including all items reasonably inferable as needed for a complete installation.

¶ 2. **Price.** The Subcontract Sum stated above includes all taxes except Washington retail sales tax on the Subcontract Sum, which Contractor pays.

¶ 3. **Prime Contract.** {s_flow}

¶ 4. **Schedule.** Subcontractor shall follow Contractor's schedule and attend the weekly subcontractor coordination meeting.

¶ 5. **Billing.** Bill monthly on the 20th on Contractor's form, with lien releases.

¶ 6. **Payment.** {s_pif} Retainage is 5%.

¶ 7. **Safety.** Subcontractor shall follow Contractor's site safety plan and Washington safety rules, and shall attend the weekly safety meeting.

¶ 8. **Changes.** Only Contractor's Project Manager may order a change, and only in writing.

¶ 9. **Notice.** {s_notice} Notice must say what happened and give a rough cost and time estimate.

¶ 10. **Pricing.** {s_price} Pricing must break out labor, material, equipment and lower-tier costs.

¶ 11. **Markup.** {s_markup}

¶ 12. **Time and material.** Tags must be signed by Contractor's superintendent on the day the work is done.

¶ 13. **Delay.** {s_delay}

¶ 14. **Insurance.** General liability of $1,000,000 per occurrence and $2,000,000 aggregate; Contractor and Owner are additional insureds.

¶ 15. **Warranty.** One year after Substantial Completion.

¶ 16. **Cleanup and protection.** Subcontractor shall clean up its debris daily, protect its installed work and the work of others until Substantial Completion, and repair any damage it causes at its own cost.

¶ 17. **Submittals and closeout.** Subcontractor shall send product data, shop drawings and samples to Contractor in time to meet the submittal schedule, and at closeout shall deliver operation and maintenance data, warranties and marked-up record drawings for the Subcontract Work.

¶ 18. **Disputes.** Disputes that involve acts of Owner or Architect follow the Prime Contract's dispute procedures. Other disputes go to mediation, then King County Superior Court.

Accepted for Contractor ({GC_NAME}) and Subcontractor ({firm}).
"""

    flow_sentence = FLOW_OVERRIDE if p["flow"] == "override" else s_flow
    flow_clause = c["notice"] if p["flow"] == "override" else c["flow"]
    notice_term = {"key": "notice_days", "value": p["notice"], "clause": c["notice"], "sentence": s_notice,
                   "unit": "business days" if p["unit"] == "business" else "calendar days"}
    pricing_term = {"key": "pricing_days", "value": p["price"], "clause": c["price"], "sentence": s_price,
                    "unit": "calendar days"}
    terms = [
        notice_term,
        {"key": "notice_flowdown", "value": flow_value, "clause": flow_clause, "sentence": flow_sentence},
        {"key": "markup_own", "value": p["mo"], "clause": c["markup"], "sentence": s_markup, "unit": "percent"},
        {"key": "markup_lower_tier", "value": p["ml"], "clause": c["markup"], "sentence": s_markup, "unit": "percent"},
        pricing_term,
        {"key": "pay_if_paid", "value": p["pif"], "clause": c["pif"], "sentence": s_pif},
        {"key": "delay_compensable", "value": v_delay, "clause": c["delay"], "sentence": s_delay},
    ]
    return md, terms


# --------------------------------------------------------------------------
# Design (Owner-Architect) summary
# --------------------------------------------------------------------------
DESIGN_TERMS = [
    ("rfi_review_days", 10, "§ 3.4.1", "Architect shall respond to each RFI from the GC/CM within 10 days after receipt."),
    ("rfi_critical_days", 3, "§ 3.4.1", "RFIs marked Critical Path shall be answered within 3 business days."),
    ("submittal_review_days", 21, "§ 3.4.2", "Architect shall review each submittal within 21 days after receipt and each resubmittal within 14 days."),
    ("resubmittal_review_days", 14, "§ 3.4.2", "Architect shall review each submittal within 21 days after receipt and each resubmittal within 14 days."),
    ("cp_review_days", 10, "§ 3.4.3", "Architect shall review each Change Proposal and send Owner a written recommendation within 10 days after receipt."),
    ("basic_fee", 1968000, "§ 11.1", "Owner shall pay Architect a stipulated sum of $1,968,000 for Basic Services."),
    ("additional_services_rate", 165, "§ 11.3", "Additional Services are billed at a blended rate of $165 per hour."),
]


def render_design():
    t = {k: s for k, _, _, s in DESIGN_TERMS}
    md = f"""# Owner-Architect Agreement: Summary

> **SYNTHETIC DOCUMENT.** A fictional summary written with AI assistance for INFO 492 C coursework. No real firm, person or project is represented. It summarizes the design agreement for the same synthetic school project as contract A.

**Owner:** {OWNER_NAME} ("Owner")
**Architect:** {ARCH_NAME} ("Architect")
**Project:** School Modernization and Addition
**Form:** Modeled on AIA Document B133-2014 (Owner-Architect, CM as Constructor edition), with Owner modifications
**Agreement date:** November 5, 2018

## Services (Article 3)

§ 3.1 Architect provides schematic design, design development, construction documents, permitting support, GC/CM procurement support and construction-phase services.

§ 3.2 Architect attends the GC/CM's weekly coordination meeting and visits the site at least once a week during construction.

§ 3.4 Construction-phase review times.

§ 3.4.1 {t['rfi_review_days']} {t['rfi_critical_days']}

§ 3.4.2 {t['submittal_review_days']}

§ 3.4.3 {t['cp_review_days']} Architect has no authority to approve changes in cost or time.

§ 3.5 Architect may issue Architect's Supplemental Instructions that do not change cost or time, and prepares Proposal Requests and Change Orders for Owner's signature.

## Owner's responsibilities (Article 5)

§ 5.1 Owner provides the hazardous materials survey, geotechnical report and existing-building survey, and Architect may rely on them.

§ 5.2 Owner's Representative is the capital projects project manager, who answers Architect's questions within 7 days.

## Compensation (Article 11)

§ 11.1 {t['basic_fee']}

§ 11.2 Construction-phase services are 20% of the basic fee and are billed monthly in equal parts over the contract time of the GC/CM agreement.

§ 11.3 {t['additional_services_rate']} Review of more than ten RFIs that the Contract Documents already answered is an Additional Service, and Owner may recover that cost from the GC/CM under the GC/CM agreement.

## Notes for readers

- The GC/CM agreement (contract A) promises the GC/CM a submittal review within 14 days and a resubmittal review within 10 days. The review times in § 3.4.2 above are longer. The Owner carries that difference.
- RFI review times in § 3.4.1 match contract A § 7.3.
"""
    terms = [{"key": k, "value": v, "clause": cl, "sentence": s} for k, v, cl, s in DESIGN_TERMS]
    return md, terms


# Prime contract terms (sentences verbatim from contract A).
PRIME_TERMS = [
    ("notice_days", 7, "§ 6.2(a)", "7 days after CM receives an RFI response, ASI, or submittal return that CM believes changes cost or time"),
    ("notice_days_direction", 7, "§ 6.2(b)", "7 days after CM receives a written or oral direction from Owner or Architect that CM believes is a change"),
    ("notice_days_other", 14, "§ 6.2(d)", "14 days after CM first knew or should have known of any other event that may increase cost or time"),
    ("cp_days", 21, "§ 6.3", "After a notice under Section 6.2, CM shall submit a CP within 21 days."),
    ("cp_days_proposal_request", 14, "§ 6.3", "If Architect issues a Proposal Request, CM shall submit a CP within 14 days after receiving it (see Exhibit E)."),
    ("markup_own", 10, "§ 6.5.2", "A subcontractor may add overhead and profit of up to 10% on its own direct cost and up to 5% on the cost of work performed by its lower-tier subcontractors."),
    ("markup_lower_tier", 5, "§ 6.5.2", "A subcontractor may add overhead and profit of up to 10% on its own direct cost and up to 5% on the cost of work performed by its lower-tier subcontractors."),
    ("markup_total_cap", 15, "§ 6.5.2", "Total markup on any portion of the work shall not exceed 15%."),
    ("fee_on_changes", 5, "§ 6.5.3", "CM may add a Fee of 5% to the direct costs and subcontractor markups of a change."),
    ("contract_time_days", 540, "§ 3.2", "CM shall achieve Substantial Completion within 540 days after the Notice to Proceed, and Final Completion within 60 days after Substantial Completion."),
    ("sgc_total", 1720000, "§ 5.2", "SGC is $1,720,000, billed as shown in Exhibit C."),
    ("sgc_daily_rate", 3185, "§ 5.2", "SGC may be increased only by CO for an extension of Contract Time, at a daily rate of $3,185 per day."),
    ("delay_compensable", "only for delays caused by Owner or Architect that are on the critical path", "§ 6.5.6",
     "A time extension is compensated only for delays caused by Owner or Architect that are on the critical path, using the SGC daily rate in Section 5.2 and with no Fee."),
    ("payment_days", 30, "§ 9.2", "Owner shall pay the approved amount within 30 days after receiving a complete Application."),
    ("liquidated_damages_per_day", 2500, "§ 3.3", "If CM fails to achieve Substantial Completion on time, CM shall pay Owner $2,500 for each day of delay."),
]


def value_forms(v):
    if isinstance(v, bool):
        return []
    if isinstance(v, int):
        return [str(v), f"{v:,}"]
    if isinstance(v, float):
        return [f"{v:g}", f"{v:,.2f}"]
    return [str(v)]


def check_term(term, text, where):
    s = term["sentence"]
    assert s in text, f"{where}: sentence for {term['key']} not verbatim: {s!r}"
    v = term["value"]
    if isinstance(v, bool):
        marks = BOOL_MARKERS[(term["key"], v)]
        assert any(m in s for m in marks), f"{where}: {term['key']}={v} not evident in {s!r}"
        other = BOOL_MARKERS[(term["key"], not v)]
        assert not any(m in s for m in other), f"{where}: {term['key']} sentence also matches the opposite value"
    else:
        assert any(f in s for f in value_forms(v)), f"{where}: value {v!r} not in sentence {s!r}"


# --------------------------------------------------------------------------
# Schedule (independent forward-pass CPM, conventions from demo4 DATA_NOTE)
# --------------------------------------------------------------------------
class Calendar:
    def __init__(self, cal, start):
        hol = set(cal["holidays"])
        wd = set(cal["workdays"])
        self.days = []
        d = dt.date.fromisoformat(start)
        end = d + dt.timedelta(days=365 * 4)
        while d <= end:
            if d.isoweekday() in wd and d.isoformat() not in hol:
                self.days.append(d.isoformat())
            d += dt.timedelta(days=1)
        self.idx = {s: i for i, s in enumerate(self.days)}

    def i(self, s):
        assert s in self.idx, f"{s} is not a working day"
        return self.idx[s]

    def first_on_or_after(self, s):
        d = dt.date.fromisoformat(s)
        while d.isoformat() not in self.idx:
            d += dt.timedelta(days=1)
        return self.idx[d.isoformat()]


def cpm(sched):
    """Forward pass. Returns {id: (start_date, finish_date, ES, EF)}."""
    cal = Calendar(sched["calendar"], sched["start"])
    acts = {a["id"]: a for a in sched["activities"]}
    preds = {k: [] for k in acts}
    succs = {k: [] for k in acts}
    for r in sched["relationships"]:
        preds[r["succ"]].append(r)
        succs[r["pred"]].append(r["succ"])
    dd = cal.first_on_or_after(sched["data_date"])
    indeg = {k: len(v) for k, v in preds.items()}
    queue = [k for k in acts if indeg[k] == 0]
    order = []
    while queue:
        k = queue.pop(0)
        order.append(k)
        for s in succs[k]:
            indeg[s] -= 1
            if indeg[s] == 0:
                queue.append(s)
    assert len(order) == len(acts), "logic loop"
    ES, EF = {}, {}
    for k in order:
        a = acts[k]
        d = a["duration"]
        if a["actual_finish"]:
            ES[k] = cal.i(a["actual_start"])
            EF[k] = ES[k] if d == 0 else cal.i(a["actual_finish"]) + 1
            continue
        if a["actual_start"]:
            ES[k] = cal.i(a["actual_start"])
            EF[k] = dd + a["remaining"]
            continue
        es = dd
        for r in preds[k]:
            p, lag = r["pred"], r["lag"]
            if r["type"] == "FS":
                es = max(es, EF[p] + lag)
            elif r["type"] == "SS":
                es = max(es, ES[p] + lag)
            elif r["type"] == "FF":
                es = max(es, EF[p] + lag - d)
            elif r["type"] == "SF":
                es = max(es, ES[p] + lag - d)
            else:
                raise ValueError(r["type"])
        con = a.get("constraint")
        if con:
            assert con["type"] == "SNET"
            es = max(es, cal.first_on_or_after(con["date"]))
        ES[k], EF[k] = es, es + d
    out = {}
    for k in acts:
        if acts[k]["duration"] == 0:
            day = max(EF[k] - 1, 0) if not acts[k]["actual_finish"] else ES[k]
            out[k] = (cal.days[day], cal.days[day], ES[k], EF[k])
        else:
            out[k] = (cal.days[ES[k]], cal.days[EF[k] - 1], ES[k], EF[k])
    return out, cal


def same_format(a, b):
    assert set(a) == set(b), (set(a) ^ set(b))
    assert set(a["calendar"]) == set(b["calendar"])
    ak = set(a["activities"][0])
    for x in b["activities"]:
        assert set(x) == ak, x
    rk = set(a["relationships"][0])
    for r in b["relationships"]:
        assert set(r) == rk, r
    assert set(b["source"]) == set(a["source"])


def check_refs(s):
    ids = [a["id"] for a in s["activities"]]
    assert len(ids) == len(set(ids)), "duplicate activity ids"
    ids = set(ids)
    for r in s["relationships"]:
        assert r["pred"] in ids and r["succ"] in ids, r
        assert r["type"] in ("FS", "SS", "FF", "SF"), r


U2_DATA_DATE = "2020-09-01"
U2_CAUSES = ["CP-0401", "CP-0402"]  # compensable, accepted, critical (demo4 DATA_NOTE)


def build_schedules():
    u1 = SCHED_U1
    # Cross-check our CPM against the bundle's printed forecast for the June update.
    sch_doc = [d for d in BUNDLE["documents"] if d["kind"] == "schedule"][0]
    fc_u1, _ = cpm(u1)
    n_checked = 0
    for p in sch_doc["pieces"]:
        m = re.match(r"(\S+) .*?Forecast (\d{4}-\d\d-\d\d) to (\d{4}-\d\d-\d\d)", p["body"])
        if m:
            aid, s, f = m.groups()
            assert fc_u1[aid][:2] == (s, f), (aid, fc_u1[aid][:2], (s, f))
            n_checked += 1
    assert n_checked == len(u1["activities"]), n_checked
    assert fc_u1["A1090"][1] == sch_doc["meta"]["forecast_substantial_completion"] == "2021-07-02"

    # Baseline: same activities and logic, no progress, data date = NTP.
    base = json.loads(json.dumps(u1))
    base["data_date"] = u1["start"]
    for a in base["activities"]:
        a["actual_start"] = a["actual_finish"] = a["remaining"] = None
    base["source"] = {"format": "json", "file": "schedule_baseline.json", "has_logic": True}
    fc_base, _ = cpm(base)
    assert fc_base["A1090"][1] == "2021-06-30", fc_base["A1090"]  # as-planned date in demo4 DATA_NOTE

    # Update 2: add accepted fragnets, forecast from the June update, then
    # record progress through the new data date as forecast (no new slips).
    u2 = json.loads(json.dumps(u1))
    wbs_of = {a["id"]: a["wbs"] for a in u2["activities"]}
    for cp in U2_CAUSES:
        fr = CASES[cp]["fragnet_truth"]
        for fa in fr["activities"]:
            succ = [r["succ"] for r in fr["relationships"] if r["pred"] == fa["id"]][0]
            new = {"id": fa["id"], "name": fa["name"], "duration": fa["duration"], "wbs": wbs_of[succ],
                   "actual_start": None, "actual_finish": None, "remaining": None, "constraint": None}
            pos = max(i for i, a in enumerate(u2["activities"])
                      if a["id"] in [r["pred"] for r in fr["relationships"] if r["succ"] == fa["id"]])
            u2["activities"].insert(pos + 1, new)
        u2["relationships"].extend(dict(r) for r in fr["relationships"])
    fc_frag, cal = cpm(u2)
    dd2 = cal.i(U2_DATA_DATE)
    for a in u2["activities"]:
        if a["actual_finish"]:
            continue
        s, f, es, ef = fc_frag[a["id"]]
        if a["duration"] == 0:
            if cal.i(s) < dd2:
                a["actual_start"] = a["actual_finish"] = s
                a["remaining"] = 0
            continue
        if es < dd2:
            a["actual_start"] = s
            if ef <= dd2:
                a["actual_finish"] = f
                a["remaining"] = 0
            else:
                a["remaining"] = ef - dd2
    u2["data_date"] = U2_DATA_DATE
    u2["source"] = {"format": "json", "file": "schedule_u2.json", "has_logic": True}
    fc_u2, _ = cpm(u2)
    for k in fc_frag:
        assert fc_u2[k][:2] == fc_frag[k][:2], (k, fc_u2[k], fc_frag[k])

    for s in (base, u2):
        same_format(u1, s)
        check_refs(s)
    check_refs(u1)
    for a in base["activities"]:
        assert a["actual_start"] is None and a["actual_finish"] is None

    def cal_days(a, b):
        return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days

    info = {
        "baseline_finish": fc_base["A1090"][1],
        "u1_finish": fc_u1["A1090"][1],
        "u2_finish": fc_u2["A1090"][1],
        "u2_delay_vs_u1_calendar": cal_days(fc_u1["A1090"][1], fc_u2["A1090"][1]),
        "u2_delay_vs_u1_workdays": fc_u2["A1090"][3] - fc_u1["A1090"][3],
        "u2_complete": sum(1 for a in u2["activities"] if a["actual_finish"]),
        "u2_in_progress": sum(1 for a in u2["activities"] if a["actual_start"] and not a["actual_finish"]),
        "u2_activities": len(u2["activities"]),
        "u2_relationships": len(u2["relationships"]),
        "bundle_forecasts_checked": n_checked,
        "fragnet_status": {fa: ("complete" if next(a for a in u2["activities"] if a["id"] == fa)["actual_finish"]
                                 else "in progress" if next(a for a in u2["activities"] if a["id"] == fa)["actual_start"]
                                 else "not started")
                           for cp in U2_CAUSES for fa in [x["id"] for x in CASES[cp]["fragnet_truth"]["activities"]]},
    }
    # Delay of each fragnet alone, from the June update, for the record.
    for cp in U2_CAUSES:
        t = json.loads(json.dumps(u1))
        fr = CASES[cp]["fragnet_truth"]
        for fa in fr["activities"]:
            t["activities"].append({"id": fa["id"], "name": fa["name"], "duration": fa["duration"], "wbs": "x",
                                    "actual_start": None, "actual_finish": None, "remaining": None, "constraint": None})
        t["relationships"].extend(fr["relationships"])
        f1, _ = cpm(t)
        info[f"delay_alone_{cp}_calendar"] = cal_days(fc_u1["A1090"][1], f1["A1090"][1])
    return base, u2, info


# --------------------------------------------------------------------------
# Sub requests
# --------------------------------------------------------------------------
# (change, firm) -> (narrative, days requested)
NARR = {
    ("CP-0201", "Cascade Plumbing"): ("RFI-112 came back adding two overflow drains on the gym roof. Our price covers the drain bodies, the leaders down to the storm tie-in and our plumber's time. No schedule impact if we get the go-ahead before the roofer closes up.", 0),
    ("CP-0202", "Northwest Door & Hardware"): ("ASI-014 bumps eight corridor doors to 90-minute. That means new rated hardware and labels on all eight. ASI says no cost but the rated sets cost more than what we bought, so here's the difference.", 0),
    ("CP-0203", "Sound Electric"): ("District wants 24 more data drops in the library. We do the boxes, rings and conduit; Lakeside pulls and terminates the Cat 6. Their quote is attached with our 5 percent on it.", 0),
    ("CP-0204", "Puget Steel Erectors"): ("Credit for deleting the bus loop walkway canopy. Steel was not fabricated yet so the full canopy package comes out, less what we already spent on shop drawings.", 0),
    ("CP-0205", "Evergreen Framing"): ("Submittal came back Approved as Noted calling for 18 gauge studs at the gym instead of 20. This is the material difference plus extra labor for the heavier stud.", 0),
    ("CP-0206", "Evergreen Framing"): ("T&M for the 14 access panels from RFI-131. All tags were signed by your super and the district rep each day. Totals below match the tags.", 0),
    ("CP-0208", "Sentinel Fire Protection"): ("ASI-022 added heads at the stage rigging. Price is heads, pipe and fitter time. The fire marshal revision fee is on your side, not in our number.", 0),
    ("CP-0209", "Cascade Plumbing"): ("Three new floor drains in the kitchen per RFI-140. Includes the drains, trap primers and saw-cut tie-in. We used our standard 15 percent.", 0),
    ("CP-0210", "Sound Electric"): ("16 smartboards need power and backing. We run the circuits; Ridgeline does the blocking. Ridgeline's number is in here with our 10 percent on it.", 0),
    ("CP-0211", "Sound Electric"): ("Four new pole lights at the staff lot per the district email. Poles, bases, fixtures, wire and trenching.", 0),
    ("CP-0212", "Clearwater Abatement"): ("Found black mastic under the classroom VCT, tested positive. Price covers removal, bagging, our crew and air monitoring. Haul-off of your dumpsters is not in our price.", 0),
    ("CP-0213", "Summit Athletic Interiors"): ("Wall padding on two gym walls per the district. Pads, Z-clips and install.", 0),
    ("CP-0214", "Timberline Casework"): ("ASI-031 changed the science room casework layout. Price is the added cabinets and rework in the shop.", 0),
    ("CP-0215", "Evergreen Flooring"): ("RFI-152 changed the stair nosings at both stairs. Remove existing, supply and set the new nosings.", 0),
    ("CP-0216", "Summit Athletic Interiors"): ("Revised bleacher anchors per RFI-158. New anchors and the extra install hours.", 0),
    ("CP-0218", "Rainier Mechanical"): ("Curb adapters for the two rooftop units per RFI-166. Adapters, sheet metal labor and flashing coordination. Lift is by others.", 0),
    ("CP-0219", "Cascade Plumbing"): ("ASI-036 adds sinks in two classrooms. Sinks, faucets, supply and waste rough and connection.", 0),
    ("CP-0220", "Clearview Glazing"): ("Solar film on the south classroom windows per district email. Film and install.", 0),
    ("CP-0221", "Sound Electric"): ("T&M for the corridor outlets. Tags attached. One day's tags didn't get the district rep's signature yet, we're chasing it.", 0),
    ("CP-0222", "Sentinel Fire Alarm"): ("RFI-171 adds strobes in the corridors. Devices, wire and programming. Our guys started on the 4th when the answer came out.", 0),
    ("CP-0223", "Northwest Door & Hardware"): ("Closers for corridor doors C201 to C212 per RFI-175. Closers, templates and install.", 0),
    ("CP-0225", "Granite Earthworks"): ("Soft organic soil at gym footing F-12. Geotech had us over-ex and replace with structural fill. Price covers the dig, haul-off, fill and compaction testing support.", 0),
    ("CP-0226", "Rainier Mechanical"): ("ASI-040 seismic bracing for all mechanical systems. Big one. Bracing hardware, engineering and install crews across both wings and the addition.", 0),
    ("CP-0226", "Sound Electric"): ("ASI-040 seismic bracing on the electrical side: conduit racks, panels and lighting. Hardware plus labor.", 0),
    ("CP-0228", "Rainier Mechanical"): ("RFI-180 moves the kitchen hood. Re-hang hood, extend the duct and rework the fire wrap.", 0),
    ("CP-0229", "Pacific Specialties"): ("Two added toilet partitions per ASI-044. Our subcontract allows 12 percent so that's what we carried.", 0),
    ("CP-0230", "Harmony Acoustics"): ("Gym sound panels per the district. Lump sum, supplied and installed.", 0),
    ("CP-0231", "Cascade Plumbing"): ("Pricing for the two emergency gas shutoffs from RFI-183, same as my email. Valves with buttons, piping and plumber time.", 0),
    ("CP-0232", "Summit Athletic Interiors"): ("Move the locker room benches per the district email. Pull, patch anchor holes, reset.", 0),
    ("CP-0233", "Pacific Specialties"): ("Four whiteboards per ASI-047. We'll pick them up at the supplier ourselves, that's the delivery line.", 0),
    ("CP-0234", "Sound Electric"): ("Three big gym fans per district email. Wiring and controls are ours; Ironwood does the mounting steel. Ironwood is at 8 percent.", 0),
    ("CP-0235", "Brightline Painting"): ("Patch and paint after abatement per ASI-050. Square footage is from our walk with your super.", 0),
    ("CP-0236", "Cascade Plumbing"): ("T&M for the four courtyard hose bibbs. Tags TM-601 to TM-603, signed by our foreman Luis each day.", 0),
    ("CP-0401", "Granite Concrete"): ("District wants a stage lift in the multipurpose room so we need a pit. Dig, form, pour and waterproof after footings and before the slab. About 6 working days of our crew, and the slab can't go until it's done.", 6),
    ("CP-0402", "Puget Steel Erectors"): ("RFI-214 changed the gym truss bearings. We have to field weld new slotted bearing assemblies after the trusses are set. Figure 4 working days of welding before deck can go on.", 4),
    ("CP-0403", "Harmony Acoustics"): ("Fabric-wrapped panels in the music and band rooms per the district letter. This is our panels and install. The blocking from Ridgeline will come separately once they price it.", 7),
    ("CP-0404", "Evergreen Site Works"): ("Second play structure and surfacing at the primary playground per the district. Equipment, footings, surfacing and install.", 0),
    ("CP-0405", "Evergreen Framing"): ("ASI-061 flips the Wing A casework to the other walls. We add new blocking and patch the old locations.", 0),
    ("CP-0406", "Summit Roofing"): ("PV-ready roof at the addition: blocking, conduit sleeves and thicker insulation under the membrane. Includes a crane pick to get the extra insulation and blocking up. Adds about 12 working days before membrane.", 12),
    ("CP-0407", "Cascade Glazing"): ("RFI-233 changed the storefront head detail. Steel subframing above every opening. Ours to furnish and install.", 0),
    ("CP-0408", "Sentinel Fire Protection"): ("ASI-070 reroutes our mains around the new duct mains and adds two zones. Pipe, heads, valves and fitter time.", 0),
    ("CP-0409", "Puget Steel Erectors"): ("Our crawler crane is tied up on another job and gets to you 5 working days late. Asking for the time and our standby while the crew waits.", 7),
    ("CP-0413", "Northwest Floors"): ("District switched the addition classrooms from VCT to rubber tile. Price is the material difference and resubmittal. New lead time is about 6 working days longer.", 6),
    ("CP-0414", "Cascade Glazing"): ("Aluminum sunshades over the south replacement windows per ASI-075.", 0),
    ("CP-0415", "Sound Electric"): ("16 data drops in the Wing B offices. We do boxes and conduit, Lakeside does the cable. Fits in with our Wing B rough-in.", 0),
    ("CP-0501", "Rainier Mechanical"): ("Room 231 is turning into an IDF, so it needs a ductless split. Unit, line set, condensate and our controls sub to tie it into the BAS.", 0),
    ("CP-0501", "Sound Electric"): ("Dedicated 30 amp circuit for the new IDF cooling unit in room 231.", 0),
    ("CP-0502", "Olympic Structural"): ("ASI-088 adds collector straps and two drag struts at the Wing B roof. Steel, connections and erection.", 0),
    ("CP-0503", "Cascade Coatings"): ("Moisture vapor mitigation coating on the addition gym slab per the district letter. Prep, coating and testing.", 0),
    ("CP-0504", "Evergreen Framing"): ("RFI-341 drops the second floor corridor ceiling 10 inches and adds soffits at the classroom doors. Framing, board and finish.", 0),
    ("CP-0504", "Rainier Mechanical"): ("Same RFI-341 change, our side: re-hang the supply mains lower and Sentinel moves their heads to the new ceiling. Sentinel's number is included.", 0),
}

# Deliberate quirks in sub_requests. See DATA_NOTE.md.
SPLIT_LOWER_TIER = {("CP-0403", "Harmony Acoustics")}   # lower tier sent as a separate, later request
MISMATCH = {
    ("CP-0406", "Summit Roofing"): "Sub's request includes a $2,500 crane pick (plus 10% markup, $2,750 in all) that the GC/CM struck before the CP, because hoisting and crane are already in NSS (contract A Exhibit C). The case's quote is the negotiated amount.",
    ("CP-0212", "Clearwater Abatement"): "Transposed total: the request's lines add to $19,140.00 (the case's quote) but the request total reads $19,410.00.",
}
TOTAL_TYPO = {("CP-0212", "Clearwater Abatement"): 19410.00}
EMAIL_LINES = {
    "CP-0231": [("Emergency gas shutoff valve with button, 2 ea", 2770.00), ("Gas piping and fittings", 940.00), ("Plumber, 18 hr", 1656.00), ("OH&P 15% on own work", 804.90)],
    "CP-0233": [("Whiteboard 4x12, installed, 4 ea", 2760.00), ("Pickup and delivery from supplier", 180.00), ("Installer, 8 hr", 560.00), ("OH&P 10% on own work", 350.00)],
    "CP-0234": [("HVLS fan wiring and controls, 3 ea", 4950.00), ("Electrician, 30 hr", 2880.00), ("Lower tier: Ironwood Structural, fan mounting steel", 9800.00), ("OH&P 10% on own work", 783.00), ("Markup 8% on lower tier", 784.00)],
    "CP-0235": [("Patch and paint walls, 2800 sf", 6020.00), ("Painter, 24 hr", 1584.00), ("OH&P 10% on own work", 760.40)],
    "CP-0236": [("Hose bibb and piping, 4 ea", 1240.00), ("Plumber, 16 hr", 1472.00), ("OH&P 10% on own work", 271.20)],
}
EMAIL_LOWER = {"CP-0234": [{"firm": "Ironwood Structural", "amount": 9800.00}]}


def pct(x):
    return f"{round(x * 100, 2):g}%"


def quote_lines(cid, q):
    if q.get("text"):
        return [{"desc": d, "amount": money(a)} for d, a in EMAIL_LINES[cid]], list(EMAIL_LOWER.get(cid, []))
    own = [{"desc": f"{l['desc']}, {l['qty']:g} {l['unit']}" if l.get("qty") is not None else l["desc"], "amount": money(l["amount"])}
           for l in q["lines"]]
    if not own and q.get("own_direct"):  # lump-sum quote with no breakdown (CP-0230)
        own = [{"desc": "Lump sum, supplied and installed (no breakdown)", "amount": money(q["own_direct"])}]
    lt_lines = [{"desc": f"Lower tier: {lt['firm']}" + (f", {lt['scope']}" if lt.get("scope") else ""), "amount": money(lt["amount"])}
                for lt in q.get("lower_tier") or []]
    rates = q.get("markup_rates_stated") or {}
    mk = []
    if q.get("markup_on_own"):
        mk.append({"desc": f"OH&P {pct(rates.get('own_work', 0))} on own work", "amount": money(q["markup_on_own"])})
    if q.get("markup_on_lower_tier"):
        mk.append({"desc": f"Markup {pct(rates.get('lower_tier', 0))} on lower tier", "amount": money(q["markup_on_lower_tier"])})
    lower = [{"firm": lt["firm"], "amount": money(lt["amount"])} for lt in q.get("lower_tier") or []]
    return own + lt_lines + mk, lower


def submitted_date(c, offset_frac=0.5, extra=0):
    ev = dt.date.fromisoformat(c["cause"]["event_date"])
    cp = dt.date.fromisoformat(c["cp_submitted"])
    span = (cp - ev).days
    off = max(1, int(span * offset_frac)) + extra
    off = min(off, max(span - 2, 0))
    d = ev + dt.timedelta(days=off)
    while d.weekday() >= 5:  # subs send on weekdays
        d -= dt.timedelta(days=1)
    if d < ev:
        d = ev
    return d.isoformat()


def build_sub_requests():
    reqs = []
    seq = {f: 0 for f in SUBS}
    # walk changes in date order so each sub's own numbers run in sequence
    items = []
    for c in CASES3 + CASES4:
        for q in c["subcontractor_quotes"]:
            items.append((c["cause"]["event_date"], c["id"], q))
    items.sort(key=lambda x: (x[0], x[1]))
    for _, cid, q in items:
        c = CASES[cid]
        f = q["firm"]
        narrative, days = NARR[(cid, f)]
        lines, lower = quote_lines(cid, q)
        assert abs(sum(l["amount"] for l in lines) - q["quote_total"]) < 0.005, (cid, f, sum(l["amount"] for l in lines), q["quote_total"])
        key_base = f"CR-{cid[3:]}-{ABBR[f]}"
        t = SUBS[f]["tmpl"]

        def number():
            seq[f] += 1
            return f"{NUM_PREFIX[t]}{seq[f]:03d}"

        if (cid, f) in SPLIT_LOWER_TIER:
            own = [l for l in lines if not l["desc"].startswith("Lower tier") and not l["desc"].startswith("Markup")]
            ltl = [l for l in lines if l["desc"].startswith("Lower tier") or l["desc"].startswith("Markup")]
            reqs.append(dict(key=key_base, number=number(), change=cid, **{"from": sub_key(f)}, to="gc",
                             submitted=submitted_date(c, 0.3), amount=money(sum(l["amount"] for l in own)), days=days,
                             narrative=narrative, lines=own, lower_tier=[]))
            reqs.append(dict(key=key_base + "-S1", number=number(), change=cid, **{"from": sub_key(f)}, to="gc",
                             submitted=submitted_date(c, 0.8), amount=money(sum(l["amount"] for l in ltl)), days=0,
                             narrative="Supplement to our earlier request: Ridgeline's price for the wall blocking behind the music room panels, with our 5 percent.",
                             lines=ltl, lower_tier=lower))
            continue
        amount = money(q["quote_total"])
        if (cid, f) == ("CP-0406", "Summit Roofing"):
            own_mk = [l for l in lines if l["desc"].startswith("OH&P")][0]
            lines = [l for l in lines if not l["desc"].startswith("OH&P")]
            lines.append({"desc": "Crane pick for added insulation and blocking", "amount": 2500.00})
            lines.append({"desc": own_mk["desc"], "amount": money(own_mk["amount"] + 250.00)})
            amount = money(sum(l["amount"] for l in lines))
        if (cid, f) in TOTAL_TYPO:
            amount = TOTAL_TYPO[(cid, f)]
        reqs.append(dict(key=key_base, number=number(), change=cid, **{"from": sub_key(f)}, to="gc",
                         submitted=submitted_date(c), amount=amount, days=days, narrative=narrative,
                         lines=lines, lower_tier=lower))
    keys = [r["key"] for r in reqs]
    assert len(keys) == len(set(keys))
    return reqs


FIELD_SAMPLES = [
    {"from": "Cascade Plumbing", "date": "2020-02-07", "name": "Luis", "becomes": "CP-0201",
     "text": "gym roof dwgs only show the 4 main drains, no overflows?? pretty sure code wants overflows. can u guys send an rfi before roofer closes it up"},
    {"from": "Granite Earthworks", "date": "2020-02-03", "name": "Tony", "becomes": "CP-0225",
     "text": "F-12 footing hole is soft organic junk down maybe 4ft. stopped digging, need geotech out here b4 we go further"},
    {"from": "Sound Electric", "date": "2020-04-02", "name": "Kyle", "becomes": "CP-0203",
     "text": "librarian asked if we could add data drops along the window wall, like 20 something. told her to go thru the district, not doing anything till we hear"},
    {"from": "Clearwater Abatement", "date": "2020-08-10", "name": "Marco", "becomes": "CP-0212",
     "text": "black mastic under the vct in the classrooms, sent sample, came back positive. bagging it now, gonna need way more haul off than planned"},
    {"from": "Puget Steel Erectors", "date": "2020-06-09", "name": "Ray", "becomes": "CP-0409",
     "text": "heads up crane is stuck on our other job, earliest it shows is a week late. office is sending a letter"},
    {"from": "Cornerstone Flatwork", "date": "2020-06-12", "name": "Sam", "becomes": "CP-0410",
     "text": "short 2 guys for the next couple wks so curbs and walks start is gonna slide, sorry"},
    {"from": "Rainier Mechanical", "date": "2020-07-15", "name": "Pete", "becomes": "CP-0504",
     "text": "2nd flr corridor supply mains hit the beams at the ceiling ht on the plans. cant make it work at 9 ft. need an answer before we hang anything"},
    {"from": "Evergreen Framing", "date": "2020-06-03", "name": "Jess", "becomes": None,
     "text": "out of 5/8 type x again on 2nd flr, truck coming tmrw am. guys moving to wing b soffits til then"},
    {"from": "Northwest Floors", "date": "2020-07-01", "name": "Ana", "becomes": None,
     "text": "cleaned up the adhesive spill in corridor b, no damage to base. all good"},
]


# --------------------------------------------------------------------------
# Schedule of values (prime contract)
# --------------------------------------------------------------------------
TRADE_CODE = {
    "Clearwater Abatement": "02-820", "Granite Earthworks": "31-200", "Cornerstone Flatwork": "32-130",
    "Evergreen Site Works": "32-310", "Granite Concrete": "03-300", "Puget Steel Erectors": "05-120",
    "Olympic Structural": "05-125", "Summit Roofing": "07-500", "Cascade Glazing": "08-400",
    "Clearview Glazing": "08-870", "Evergreen Framing": "09-210", "Brightline Painting": "09-900",
    "Northwest Floors": "09-650", "Evergreen Flooring": "09-651", "Timberline Casework": "06-410",
    "Northwest Door & Hardware": "08-100", "Pacific Specialties": "10-200", "Harmony Acoustics": "09-840",
    "Summit Athletic Interiors": "11-660", "Cascade Plumbing": "22-000", "Rainier Mechanical": "23-000",
    "Sound Electric": "26-000", "Sentinel Fire Protection": "21-000", "Sentinel Fire Alarm": "28-310",
    "Cascade Coatings": "09-960",
}
SUBCONTRACT_WORK = 19150000
SGC_LINES = [
    ("01-310", "Project Manager (SGC)", 360000, "time"),
    ("01-311", "Superintendent (SGC)", 520000, "time"),
    ("01-312", "Project Engineer (SGC)", 280000, "time"),
    ("01-313", "Safety and quality staff (SGC)", 180000, "time"),
    ("01-500", "Field office and trailers, monthly rental (SGC)", 120000, "time"),
    ("01-501", "Field office and trailers, mobilize and demobilize (SGC)", 30000, "fixed"),
    ("01-510", "Project vehicles and small tools (SGC)", 90000, "time"),
    ("01-520", "Document reproduction (SGC)", 60000, "fixed"),
    ("01-580", "Signage and miscellaneous (SGC)", 80000, "fixed"),
]
NSS_LINES = [
    ("01-511", "Temporary power and lighting (NSS)", 120000),
    ("01-540", "Site security and fencing (NSS)", 95000),
    ("01-512", "Temporary sanitary facilities (NSS)", 40000),
    ("01-740", "Dumpsters and haul-off (NSS)", 140000),
    ("01-545", "Hoisting and crane (NSS)", 215000),
]
SPW_LINES = [
    ("06-100", "Self-performed rough carpentry and blocking", 1150000),
    ("02-410", "Self-performed selective demolition", 900000),
    ("08-710", "Self-performed door and Division 10 installation", 650000),
    ("01-740S", "Self-performed cleanup and final cleaning", 600000),
]


def build_sov():
    sov = []
    sub_total = 0
    for f in firm_order:
        sov.append({"contract": "prime", "code": TRADE_CODE[f], "description": f"{firm_trade[f]}, subcontract with {f}",
                    "amount": SUBS[f]["amount"], "general_conditions": False, "basis": "fixed", "subcontract": sub_key(f)})
        sub_total += SUBS[f]["amount"]
    elevator = 310000
    other = SUBCONTRACT_WORK - sub_total - elevator
    assert other > 0, other
    sov.append({"contract": "prime", "code": "14-210", "description": "Elevator, subcontract not yet awarded", "amount": elevator,
                "general_conditions": False, "basis": "fixed", "subcontract": None})
    sov.append({"contract": "prime", "code": "32-900", "description": "Landscaping, irrigation, signage and other trades, subcontracts not yet awarded",
                "amount": other, "general_conditions": False, "basis": "fixed", "subcontract": None})
    for code, d, a in SPW_LINES:
        sov.append({"contract": "prime", "code": code, "description": d, "amount": a, "general_conditions": False, "basis": "fixed"})
    for code, d, a, b in SGC_LINES:
        sov.append({"contract": "prime", "code": code, "description": d, "amount": a, "general_conditions": True, "basis": b})
    for code, d, a in NSS_LINES:
        sov.append({"contract": "prime", "code": code, "description": d, "amount": a, "general_conditions": False, "basis": "fixed"})
    sov.append({"contract": "prime", "code": "01-900", "description": "CM's Fee (5% of subcontract work and SPW)", "amount": 1122500,
                "general_conditions": False, "basis": "fixed"})
    sov.append({"contract": "prime", "code": "01-950", "description": "CM Contingency", "amount": 338007,
                "general_conditions": False, "basis": "fixed"})
    # Ties to contract A Exhibit A and C
    assert sum(x["amount"] for x in sov) == 26240507
    assert sum(a for _, _, a, _ in SGC_LINES) == 1720000
    assert sum(a for _, _, a in NSS_LINES) == 610000
    assert sum(a for _, _, a in SPW_LINES) == 3300000
    assert sum(x["amount"] for x in sov if x.get("subcontract", "x") is not None and "subcontract" in x) + elevator + other == SUBCONTRACT_WORK
    codes = [x["code"] for x in sov]
    assert len(codes) == len(set(codes))
    return sov


# --------------------------------------------------------------------------
# Answer key helpers
# --------------------------------------------------------------------------
def min_calendar_span(business_days):
    """Fewest calendar days after an event in which N business days can fall
    (weekends only; holidays only lengthen it)."""
    best = None
    for start_wd in range(7):
        d, n, cal = start_wd, 0, 0
        while n < business_days:
            d = (d + 1) % 7
            cal += 1
            if d < 5:
                n += 1
        best = cal if best is None else min(best, cal)
    return best


def main():
    DOCS.mkdir(parents=True, exist_ok=True)

    # ---- prime contract terms
    prime_terms = []
    for k, v, cl, s in PRIME_TERMS:
        t = {"key": k, "value": v, "clause": cl, "sentence": s}
        check_term_plain(t, CONTRACT_A_TEXT, "contract A (demo1)")
        check_term_plain(t, CONTRACT_A_PIECES, "contract A (bundle pieces)")
        prime_terms.append(t)

    # ---- design summary
    design_md, design_terms = render_design()
    write_text(DOCS / "design_summary.md", design_md)
    dtext = (DOCS / "design_summary.md").read_text(encoding="utf-8")
    for t in design_terms:
        check_term_plain(t, dtext, "design_summary.md")

    # ---- companies
    companies = [
        {"key": "owner", "name": OWNER_NAME, "kind": "owner"},
        {"key": "architect", "name": ARCH_NAME, "kind": "architect"},
        {"key": "gc", "name": GC_NAME, "kind": "gc"},
    ]
    for f in firm_order:
        companies.append({"key": sub_key(f), "name": f, "kind": "sub", "trade": firm_trade[f], "tier": 1})
    lt_parents = {}
    for lf, parent, cid in lower_tier_seen:
        lt_parents.setdefault(lf, [])
        if parent not in lt_parents[lf]:
            lt_parents[lf].append(parent)
    lt_trade = {"Lakeside Low Voltage": "Low voltage cabling", "Ridgeline Carpentry": "Rough carpentry and blocking",
                "Northwest Controls": "Building automation controls", "Ironwood Structural": "Miscellaneous steel"}
    lower_tier_skipped = []
    for lf, parents in lt_parents.items():
        if lf in SUBS:  # already a first-tier sub (Sentinel Fire Protection under Rainier on CP-0504)
            lower_tier_skipped.append({"firm": lf, "also_lower_tier_under": [sub_key(p) for p in parents]})
            continue
        entry = {"key": sub_key(lf), "name": lf, "kind": "sub", "trade": lt_trade[lf], "tier": 2, "parent": sub_key(parents[0])}
        if len(parents) > 1:
            entry["also_under"] = [sub_key(p) for p in parents[1:]]
        companies.append(entry)
    ckeys = [c["key"] for c in companies]
    assert len(ckeys) == len(set(ckeys))

    # ---- contracts
    contracts = [
        {"key": "prime", "kind": "prime", "up": "owner", "down": "gc", "parent": None,
         "title": CONTRACT_DOC["title"], "document_key": CONTRACT_DOC["key"], "file": None,
         "source_file": "demo1/data/synthetic_contract.md", "terms": prime_terms},
        {"key": "design", "kind": "design", "up": "owner", "down": "architect", "parent": None,
         "title": "Owner-Architect Agreement (summary)", "file": rel(DOCS / "design_summary.md"), "terms": design_terms},
    ]
    sub_terms = {}
    for f in firm_order:
        p = SUBS[f]
        md, terms = render_subcontract(f, p)
        path = DOCS / f"subcontract_{slug(f).replace('-', '_')}.md"
        write_text(path, md)
        text = path.read_text(encoding="utf-8")
        for t in terms:
            check_term(t, text, path.name)
        words = len(text.split())
        assert 450 <= words <= 1100, (path.name, words)  # about 1 to 2 pages
        for clause_word in ("Prime Contract", "notice", "markup" if p["tmpl"] != "B" else "Overhead and profit", "Payment"):
            assert clause_word.lower() in text.lower(), (path.name, clause_word)
        sub_terms[f] = {t["key"]: t for t in terms}
        assert set(sub_terms[f]) == {"notice_days", "notice_flowdown", "markup_own", "markup_lower_tier",
                                     "pricing_days", "pay_if_paid", "delay_compensable"}
        contracts.append({"key": sub_key(f), "kind": "sub", "up": "gc", "down": sub_key(f), "parent": "prime",
                          "title": f"Subcontract: {firm_trade[f]} ({f})", "file": rel(path), "amount": p["amount"],
                          "executed": p["date"], "terms": terms})

    # ---- SOV
    sov = build_sov()

    # ---- schedules
    base, u2, sched_info = build_schedules()
    write_json(PLAT / "schedule_baseline.json", base)
    write_json(PLAT / "schedule_u2.json", u2)
    for name in ("schedule_baseline.json", "schedule_u2.json"):
        reloaded = json.loads((PLAT / name).read_text(encoding="utf-8"))
        same_format(SCHED_U1, reloaded)
        check_refs(reloaded)
    schedule_versions = [
        {"key": "baseline", "label": "Baseline", "data_date": base["data_date"], "file": rel(PLAT / "schedule_baseline.json"),
         "caused_by": None, "forecast_substantial_completion": sched_info["baseline_finish"]},
        {"key": "u1", "label": "Update 1", "data_date": SCHED_U1["data_date"], "file": "demo4/data/schedule.json",
         "caused_by": None, "forecast_substantial_completion": sched_info["u1_finish"]},
        {"key": "u2", "label": "Update 2", "data_date": u2["data_date"], "file": rel(PLAT / "schedule_u2.json"),
         "caused_by": list(U2_CAUSES), "forecast_substantial_completion": sched_info["u2_finish"]},
    ]
    for sv in schedule_versions:
        s = load_json(sv["file"])
        assert s["data_date"] == sv["data_date"]
    assert u2["data_date"] > SCHED_U1["data_date"] > base["data_date"]
    for cp in U2_CAUSES:
        c = CASES[cp]
        assert c["time"]["cause_party"] in ("owner", "architect") and not c["time"]["concurrent"], cp
        for fa in c["fragnet_truth"]["activities"]:
            assert any(a["id"] == fa["id"] for a in u2["activities"]), fa

    # ---- sub requests
    reqs = build_sub_requests()
    for r in reqs:
        assert r["from"] in ckeys and r["to"] in ckeys and r["change"] in CASES
        k = (r["change"], next(f for f in SUBS if sub_key(f) == r["from"]))
        line_sum = money(sum(l["amount"] for l in r["lines"]))
        if k in TOTAL_TYPO:
            assert line_sum != r["amount"]
        else:
            assert abs(line_sum - r["amount"]) < 0.005, (r["key"], line_sum, r["amount"])
        c = CASES[r["change"]]
        assert c["cause"]["event_date"] <= r["submitted"] <= c["cp_submitted"], (r["key"], r["submitted"])

    # ---- field samples
    fields = []
    for fs in FIELD_SAMPLES:
        assert fs["from"] in SUBS
        assert fs["becomes"] is None or fs["becomes"] in CASES
        fields.append({"from": sub_key(fs["from"]), "date": fs["date"], "text": fs["text"], "name": fs["name"], "becomes": fs["becomes"]})

    platform = {
        "meta": {"synthetic": True,
                 "note": ("Synthetic sample data for the shared platform, written with AI assistance for INFO 492 C coursework. "
                          "No real firm, person or project. Extends the synthetic school project in record/bundle.json. "
                          "Rebuild with python3 record/platform/build/build.py; see record/platform/DATA_NOTE.md."),
                 "built": BUILT},
        "project": {"name": BUNDLE["project"]["name"], "contract_type": "gccm"},
        "companies": companies,
        "contracts": contracts,
        "sov": sov,
        "schedule_versions": schedule_versions,
        "sub_requests": reqs,
        "field_samples": fields,
    }

    # ---------------- answer key ----------------
    flow = {}
    for f in firm_order:
        t = sub_terms[f]
        n = t["notice_days"]["value"]
        unit = SUBS[f]["unit"]
        cal_min = min_calendar_span(n) if unit == "business" else n
        margin = PRIME_NOTICE_DAYS - cal_min
        price = t["pricing_days"]["value"]
        flow[sub_key(f)] = {
            "notice_days": n,
            "notice_unit": "business days" if unit == "business" else "calendar days",
            "notice_calendar_days": cal_min,
            "notice_flowdown": t["notice_flowdown"]["value"],
            "prime_notice_days": PRIME_NOTICE_DAYS,
            "gc_days_left": margin,
            "gap": margin <= 0,
            "short_by_days": max(0, -margin),
            "gc_days_left_other_events": PRIME_NOTICE_OTHER_DAYS - cal_min,
            "pricing_days": price,
            "gc_days_left_to_submit_cp": PRIME_CP_DAYS - price,
            "gc_days_left_after_proposal_request": PRIME_PR_DAYS - price,
        }
    gaps = [k for k, v in flow.items() if v["gap"]]
    clean = [k for k, v in flow.items() if not v["gap"]]
    assert len(gaps) >= 2 and len(clean) >= 1
    # every gap is unambiguous: no sub sits at a 0 or 1 day margin
    for v in flow.values():
        assert v["gc_days_left"] >= 2 or v["gc_days_left"] <= -3, v

    time_total = sum(a for _, _, a, b in SGC_LINES if b == "time")
    sgc_total = sum(a for _, _, a, _ in SGC_LINES)
    per_day = round(time_total / CONTRACT_DAYS, 2)
    assert abs(sum(x["amount"] for x in sov if x["general_conditions"] and x["basis"] == "time") - time_total) < 0.01
    agree = abs(per_day - STATED_RATE) / STATED_RATE <= 0.01
    cost_per_day = {
        "sov_time_based_gc_total": time_total,
        "sov_time_based_lines": [x["code"] for x in sov if x["general_conditions"] and x["basis"] == "time"],
        "contract_days": CONTRACT_DAYS,
        "contract_days_basis": "contract A § 3.2: Substantial Completion within 540 days after Notice to Proceed",
        "sov_cost_per_day": per_day,
        "contract_stated_rate": STATED_RATE,
        "contract_stated_rate_clause": "§ 5.2",
        "difference_per_day": round(STATED_RATE - per_day, 2),
        "difference_pct_of_sov_rate": round((STATED_RATE - per_day) / per_day * 100, 1),
        "agree": agree,
        "tolerance": "agree means within 1% of the stated rate",
        "explanation": (f"The stated rate equals all SGC (${sgc_total:,}) / 540 = ${sgc_total / CONTRACT_DAYS:,.2f}, which includes "
                        f"fixed SOV lines (mobilization, reproduction, signage, ${sgc_total - time_total:,}) that do not grow with time. "
                        f"Time-based lines alone give ${per_day:,.2f} per day."),
        "alternative_basis_600_days": round(time_total / 600, 2),
    }
    assert not agree

    rollups = {}
    for cid in sorted({r["change"] for r in reqs}):
        rs = [r for r in reqs if r["change"] == cid]
        s = money(sum(r["amount"] for r in rs))
        qt = money(sum(q["quote_total"] for q in CASES[cid]["subcontractor_quotes"]))
        diff = money(s - qt)
        mism = [MISMATCH[k] for k in MISMATCH if k[0] == cid]
        entry = {"requests": [r["key"] for r in rs], "sub_requests_total": s, "case_quotes_total": qt,
                 "difference": diff, "match": abs(diff) < 0.005}
        if mism:
            entry["deliberate_mismatch"] = True
            entry["reason"] = " ".join(mism)
            assert not entry["match"], cid
        else:
            assert entry["match"], (cid, s, qt)
        rollups[cid] = entry
    assert sum(1 for v in rollups.values() if v.get("deliberate_mismatch")) == len(MISMATCH)

    visibility = {}
    for c in companies:
        k = c["key"]
        if k == "gc":
            vis = [r["key"] for r in reqs if r["to"] == "gc"]
        elif k in ("owner", "architect"):
            vis = []
        else:
            vis = [r["key"] for r in reqs if r["from"] == k]
        visibility[k] = vis

    answer_key = {
        "meta": {"synthetic": True, "built": BUILT,
                 "note": "Computed by record/platform/build/build.py from the data in platform.json and the cases; written with AI assistance."},
        "flowdown_gaps": {
            "rule": ("gc_days_left = prime notice window (contract A § 6.2(a)-(c), 7 calendar days) minus the sub's notice window in calendar days "
                     "(business days converted to the fewest calendar days they can span). A gap is gc_days_left <= 0: the sub may give notice "
                     "on or after the day the GC/CM's own notice to Owner is due. The operative window is the one the subcontract makes govern."),
            "subs": flow,
            "gap_subs": gaps,
            "clean_subs": clean,
        },
        "cost_per_day": cost_per_day,
        "rollups": rollups,
        "visibility": {
            "rule": "A sub sees only its own requests; the GC/CM sees all requests sent to it; Owner and Architect see none (they see the GC/CM's proposal).",
            "by_company": visibility,
        },
        "extra_checks": {
            "markup_above_prime": [{"sub": sub_key(f), "term": k, "sub_value": sub_terms[f][k]["value"], "prime_value": pv}
                                   for f in firm_order for k, pv in (("markup_own", 10), ("markup_lower_tier", 5))
                                   if sub_terms[f][k]["value"] > pv],
            "design_vs_prime_review_times": [
                {"item": "submittal review", "design_agreement_days": 21, "prime_contract_days": 14, "prime_clause": "§ 8.2", "design_clause": "§ 3.4.2"},
                {"item": "resubmittal review", "design_agreement_days": 14, "prime_contract_days": 10, "prime_clause": "§ 8.2", "design_clause": "§ 3.4.2"},
            ],
            "schedule": sched_info,
            "first_tier_firm_also_lower_tier": lower_tier_skipped,
        },
    }

    write_json(PLAT / "platform.json", platform)
    write_json(PLAT / "answer_key.json", answer_key)
    write_text(PLAT / "DATA_NOTE.md", data_note(platform, answer_key, sched_info))

    # final re-load checks
    pj = json.loads((PLAT / "platform.json").read_text(encoding="utf-8"))
    for c in pj["contracts"]:
        if c.get("file"):
            text = (ROOT / c["file"]).read_text(encoding="utf-8")
            for t in c["terms"]:
                (check_term if c["kind"] == "sub" else check_term_plain)(t, text, c["file"])
    print(f"OK: {len(companies)} companies, {len(contracts)} contracts, {len(sov)} SOV lines, "
          f"{len(reqs)} sub_requests over {len(rollups)} changes, {len(fields)} field samples")
    print(f"flow-down gaps: {gaps}")
    print(f"cost per day: SOV {per_day} vs stated {STATED_RATE} (agree={agree})")
    print(f"schedules: {json.dumps(sched_info)}")


def check_term_plain(t, text, where):
    s = t["sentence"]
    assert s in text, f"{where}: not verbatim: {s!r}"
    assert any(f in s for f in value_forms(t["value"])), f"{where}: value {t['value']!r} not in {s!r}"


def data_note(pj, ak, si):
    fl = ak["flowdown_gaps"]["subs"]
    name = {c["key"]: c["name"] for c in pj["companies"]}
    rows = "\n".join(
        f"| {name[k]} | {v['notice_days']} {v['notice_unit']} | {'yes' if v['notice_flowdown'] else 'no'} | "
        f"{v['gc_days_left']} | {'**gap**' if v['gap'] else 'clean'} | {v['pricing_days']} |"
        for k, v in fl.items())
    cpd = ak["cost_per_day"]
    mism = "\n".join(f"- **{cid}**: requests ${v['sub_requests_total']:,.2f} vs case quotes ${v['case_quotes_total']:,.2f}. {v['reason']}"
                     for cid, v in ak["rollups"].items() if v.get("deliberate_mismatch"))
    return f"""# Platform sample data: data note

## What is synthetic
Everything in `record/platform/` is synthetic test data, written with AI assistance (an AI assistant working as an independent data writer) for INFO 492 C coursework. No real firm, person or project is represented. Company names come from the existing synthetic cases and bundle; the Owner, Architect and GC/CM names are the placeholders already used in contract A and the bundle (none were invented). Field-sample first names are invented.

The writer read only the data files listed in `SPEC.md` (the bundle, contract A, the demo3 and demo4 cases, the June 2020 schedule and its data note). It did not open any code in `assets/`, `record/*.py`, `demo3/*.py`, `demo4/*.py` or `tools/`.

## How it was built
Run `python3 record/platform/build/build.py` from the repo root (standard library only). It rewrites every file here and stops on any failed check:
- `platform.json`: {len(pj['companies'])} companies, {len(pj['contracts'])} contracts (prime, design, {len(pj['contracts']) - 2} subcontracts), {len(pj['sov'])} SOV lines, 3 schedule versions, {len(pj['sub_requests'])} sub requests on {len(ak['rollups'])} changes, {len(pj['field_samples'])} field samples.
- `docs/`: one subcontract per first-tier sub (three different forms: "§" agreement, "Section" short form, "¶" trade form) and `design_summary.md`.
- `schedule_baseline.json`, `schedule_u2.json`: same format as `demo4/data/schedule.json`.
- `answer_key.json`: flow-down gaps, cost per day, rollups, visibility, plus extra checks.

Checks the script asserts: every term sentence is verbatim in its contract file (prime terms in both `demo1/data/synthetic_contract.md` and the bundle's contract pieces) and contains its value (numbers as written, with or without thousands commas; text values as substrings; booleans by a marker phrase such as "is a condition precedent" vs "is not a condition precedent", with the opposite marker absent); sub request amounts match the cases' `subcontractor_quotes` per change except the deliberate mismatches; request lines add to the request amount (except the one transposed total); at least two flow-down gaps and at least one clean subcontract; the SOV ties to contract A Exhibits A and C ($26,240,507); schedule files load as JSON with the same keys as the June update; every relationship references an existing activity id.

The schedules come from an independent forward-pass CPM in `build.py` using the conventions in `demo4/data/DATA_NOTE.md`. It reproduces all {si['bundle_forecasts_checked']} forecast dates printed in the bundle's June 2020 schedule document and the as-planned finish of 2021-06-30.

## Companies and subcontracts
First-tier subs are every firm in the cases' `subcontractor_quotes`, plus Cornerstone Flatwork (named in the bundle's 2020-06-15 letter, the unnamed flatwork sub on CP-0410). Lower-tier firms (tier 2) are Lakeside Low Voltage and Ridgeline Carpentry (under Sound Electric; Ridgeline is also under Harmony Acoustics, listed in `also_under`), Northwest Controls (under Rainier Mechanical) and Ironwood Structural (under Sound Electric, named only in the CP-0234 email quote). Lower-tier firms have no subcontract with the GC/CM.

| Sub | Notice window | Prime notice flows down | GC days left (7 - window) | Result | Pricing days |
|---|---|---|---|---|---|
{rows}

## Deliberate quirks
- **Flow-down gaps.** Granite Earthworks (14 days), Harmony Acoustics (21 days), Puget Steel Erectors (10 *business* days: at least 12 calendar days if the event falls on a weekend, 14 if on a weekday; the key uses the shortest, 12) and Summit Roofing (10 days). Summit Roofing's § 2.1 is a general flow-down that names notice procedures, but § 4.2 says "Notwithstanding § 2.1, the notice period in this § 4.2 governs", so its `notice_flowdown` is false and the 10-day window governs. All other subs are clean with 2 to 5 calendar days; no sub sits at a 0 or 1 day margin, so the result does not depend on how one counts the GC's turnaround.
- **Pricing windows.** Rainier Mechanical has 21 days to price a change, which uses the GC/CM's whole 21-day CP window (§ 6.3) and is 7 days over a 14-day Proposal Request window. Harmony Acoustics has 14 days (0 days left after a Proposal Request).
- **Markups above the prime contract.** Pacific Specialties' subcontract allows 12% on its own work and Sound Electric's allows 10% on lower-tier work; contract A § 6.5.2 allows 10% and 5%. These match the quotes in CP-0229 and CP-0210. Cascade Plumbing's subcontract says 10%, so its 15% quotes (CP-0209, CP-0231) break both contracts.
- **Cost per day.** Time-based SGC lines in the SOV total ${cpd['sov_time_based_gc_total']:,}, or ${cpd['sov_cost_per_day']:,.2f} per day over 540 days. Contract A § 5.2 states $3,185 per day, which is all SGC (${sgc_total_str()}) / 540 and so includes fixed lines (trailer mobilization, reproduction, signage). The two disagree by ${cpd['difference_per_day']:,.2f} per day. NSS lines are not counted as general conditions, because contract A ties the daily rate to SGC only.
- **Sub request mismatches** (marked `deliberate_mismatch` in the answer key):
{mism}
- **Split request.** Harmony Acoustics sent CP-0403 in two requests: its own work first, then a supplement (`-S1`) with Ridgeline Carpentry's lower-tier price and markup. Together they match the case quote, so the rollup must sum both.
- **Firm in two tiers.** Sentinel Fire Protection is a first-tier sub and also a lower tier under Rainier Mechanical on CP-0504. It is listed once, as tier 1.
- **Design agreement review times.** `design_summary.md` gives the Architect 21 days for submittals and 14 for resubmittals; contract A § 8.2 promises the GC/CM 14 and 10. RFI times match.
- **Update 2.** Data date {pj['schedule_versions'][2]['data_date']}, caused by {', '.join(pj['schedule_versions'][2]['caused_by'])} (Owner and Architect changes, both compensable in the demo4 answer key). Their fragnet activities are added with the cases' own ids and logic. Progress through the data date follows the forecast exactly (no new slips): {si['u2_complete']} activities complete, {si['u2_in_progress']} in progress. Forecast Substantial Completion moves from {si['u1_finish']} to {si['u2_finish']} ({si['u2_delay_vs_u1_calendar']} calendar days; alone, CP-0401 gives {si['delay_alone_CP-0401_calendar']} and CP-0402 gives {si['delay_alone_CP-0402_calendar']}).
- **Baseline.** Same activities, durations and logic as the June update, no actuals, data date 2020-02-03. The June update's slips are in its actual dates, not its durations, so the baseline finish is 2021-06-30.

## Limits
- One writer produced the contracts, requests and answer key, so the key checks consistency with this writer's reading, not an independent legal review.
- Sub request narratives are short and cleaner than real ones. Submitted dates are placed between each change's event and CP dates by a fixed rule.
- Update 2 has no out-of-sequence progress or new slips.
"""


def sgc_total_str():
    return f"{sum(a for _, _, a, _ in SGC_LINES):,}"


if __name__ == "__main__":
    main()
