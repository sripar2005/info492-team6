#!/usr/bin/env python3
"""Build the SYNTHETIC project record for ClauseStream (INFO 492 C).

Writes record/bundle.json (the import format the app loads) and one readable
Markdown file per document under record/docs/<kind>/<number>.md.

Standard library only. Deterministic: a fixed seed, sorted inputs, and no
timestamps, so re-running gives byte-identical output.

Run from anywhere:  python3 record/build_record.py
Reads (never modifies): demo1/data/synthetic_contract.md, demo3/data/cases.json,
demo4/data/cases.json, demo4/data/schedule.json, demo4/data/schedule.csv.
"""
import csv
import datetime as dt
import json
import os
import random
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "record")
SEED = 4922020
# Numbers of documents that have been replaced by real ones (loaded with source upload/procore).
# They are still generated for the self-check, but left out of bundle.json and record/docs/;
# links to them stay in the bundle and resolve to the real document by number on import.
REPLACED = set()
RNG = random.Random(SEED)

SYN_NOTE = ("> SYNTHETIC DOCUMENT. AI-assisted, written for INFO 492 C coursework. "
            "Not a real project, firm, or person. Replace with the real document when available.")

PROJECT = {
    "name": "School Modernization and Addition (synthetic)",
    "owner_org": "Example School District No. 1",
    "synthetic": True,
}

OWNER_REP = "M. Okafor, Owner's Representative (Example School District No. 1)"
ARCH = "L. Chen, Project Architect (Example Architecture, PLLC)"
CM_PM = "J. Park, CM Project Manager (Example Builders, Inc.)"
CM_SUPT = "D. Alvarez, CM Superintendent (Example Builders, Inc.)"


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


def d(s):
    return dt.date.fromisoformat(s)


def iso(x):
    return x.isoformat()


def add_days(s, n):
    return iso(d(s) + dt.timedelta(days=n))


def money(x):
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.2f}"


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
with open(os.path.join(ROOT, "demo1/data/synthetic_contract.md"), encoding="utf-8") as f:
    CONTRACT_MD = f.read()
with open(os.path.join(ROOT, "demo3/data/cases.json"), encoding="utf-8") as f:
    CASES3 = json.load(f)["cases"]
with open(os.path.join(ROOT, "demo4/data/cases.json"), encoding="utf-8") as f:
    CASES4 = json.load(f)["cases"]
with open(os.path.join(ROOT, "demo4/data/schedule.json"), encoding="utf-8") as f:
    SCHED = json.load(f)
with open(os.path.join(ROOT, "demo4/data/schedule.csv"), encoding="utf-8", newline="") as f:
    SCHED_CSV = {r["Activity ID"]: r for r in csv.DictReader(f)}

CASES = [(c, "demo3") for c in CASES3] + [(c, "demo4") for c in CASES4]
ACT = {a["id"]: a for a in SCHED["activities"]}
HOLIDAYS = set(SCHED["calendar"]["holidays"])
SPAN_START = SCHED["start"]
SPAN_END = max(r["Finish"] for r in SCHED_CSV.values() if r["Finish"])


def workday(s):
    x = d(s)
    return x.weekday() < 5 and s not in HOLIDAYS


# ---------------------------------------------------------------------------
# Bundle helpers
# ---------------------------------------------------------------------------
DOCS = []          # in insertion order
DOC_BY_KEY = {}
LINKS = []
FOLDER = {"contract": "contract", "spec": "spec", "rfi": "rfi", "asi": "asi", "submittal": "submittal",
          "schedule": "schedule", "daily_report": "daily_report", "minutes": "minutes",
          "change_order": "change_order", "other": "other"}


def fname(number):
    return re.sub(r"[^A-Za-z0-9.\-]+", "_", number).strip("_") + ".md"


def add_doc(kind, number, title, issued_on, author_party, meta, pieces):
    assert number not in DOC_BY_KEY, f"duplicate key {number}"
    ps = []
    for i, (section, body, piece_date, party) in enumerate(pieces, 1):
        ps.append({"ordinal": i, "section": section, "body": body, "piece_date": piece_date, "party": party})
    doc = {
        "key": number, "kind": kind, "number": number, "title": title, "issued_on": issued_on,
        "author_party": author_party, "source": "synthetic", "external_id": f"syn:{number}",
        "file": f"record/docs/{FOLDER[kind]}/{fname(number)}", "meta": meta, "pieces": ps,
    }
    DOCS.append(doc)
    DOC_BY_KEY[number] = doc
    return doc


def link(frm, to, relation, note, from_section=None, to_section=None):
    LINKS.append({"from": frm, "to": to, "relation": relation, "from_section": from_section,
                  "to_section": to_section, "note": note})


# ---------------------------------------------------------------------------
# 1. Contract A (pieces = clauses, parsed from demo1)
# ---------------------------------------------------------------------------
def unemph(s):
    s = s.replace("**", "")
    return re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"\1", s)


def parse_contract(md):
    lines = md.split("\n")
    pieces = []          # (section, body)
    cur_sec, cur = None, []

    def flush():
        if cur_sec is not None:
            body = "\n".join(cur).strip()
            if body:
                pieces.append((cur_sec, unemph(body)))

    # Preamble: everything before the first Article heading, without the H1.
    i = 0
    pre = []
    while i < len(lines) and not lines[i].startswith("## "):
        if not lines[i].startswith("# "):
            pre.append(lines[i])
        i += 1
    pieces.append(("Preamble", unemph("\n".join(pre).strip())))
    exhibit = None
    for line in lines[i:]:
        m_art = re.match(r"^## (Article \d+)\.", line)
        m_exh = re.match(r"^## (Exhibit [A-E])\.", line)
        m_cl = re.match(r"^\*\*(\d+\.\d+)(?:\*\*)?\s+(.*)$", line)
        m_sub = re.match(r"^- \*\*(\d+\.\d+\.\d+)\s+(.*)$", line)
        m_ex_sec = re.match(r"^\*\*Section (\d\d \d\d \d\d)\.\s+(.*)$", line)
        if m_art:
            flush(); cur_sec, cur, exhibit = None, [], None
        elif m_exh:
            flush(); exhibit = m_exh.group(1); cur_sec, cur = exhibit, [line[3:].split(". ", 1)[1]]
        elif m_cl and exhibit is None:
            flush(); cur_sec, cur = m_cl.group(1), [("**" if line.startswith("**" + m_cl.group(1) + " ") else "") + m_cl.group(2)]
        elif m_sub and exhibit is None:
            flush(); cur_sec, cur = m_sub.group(1), ["**" + m_sub.group(2)]
        elif m_ex_sec and exhibit == "Exhibit E":
            flush(); cur_sec, cur = f"Exhibit E {m_ex_sec.group(1)}", ["**Section " + m_ex_sec.group(1) + ". " + m_ex_sec.group(2)]
        else:
            if cur_sec is not None:
                cur.append(line)
    flush()
    return pieces


CONTRACT_PIECES = parse_contract(CONTRACT_MD)
add_doc("contract", "Contract A",
        "Agreement Between Owner and Construction Manager as Constructor (GC/CM), GMP $26,240,507",
        "2019-06-17", "owner",
        {"source_file": "demo1/data/synthetic_contract.md", "form": "Modeled on AIA A133-2009 with Owner modifications",
         "gmp": 26240507, "contract_time_days": 540, "notice_to_proceed": "2020-02-03",
         "split_rule": "one piece per numbered clause (sub-clauses 6.5.x separate), one per exhibit; Exhibit E split by spec section; markdown emphasis removed, text otherwise verbatim"},
        [(s, b, "2019-06-17", "owner") for s, b in CONTRACT_PIECES])
CONTRACT_SECTIONS = {s for s, _ in CONTRACT_PIECES}

# ---------------------------------------------------------------------------
# 2. Specifications (Division 01 and technical sections), bid set
# ---------------------------------------------------------------------------
SPEC_DATE = "2019-05-17"
SPECS = [
    ("01 26 00", "Contract Modification Procedures", [
        ("1.01.A", "Summary. This Section states the procedures for Proposal Requests, Change Proposals (CPs), Construction Change Directives, and Change Orders. Article 6 of the Agreement controls if this Section conflicts with it."),
        ("1.02.A", "Proposal Requests. Architect may issue a written Proposal Request describing a possible change. CM shall return a CP within 14 days after receiving it, or within that time explain in writing why more time is needed."),
        ("1.03.A", "Change Proposal content. Each CP shall reference the RFI, ASI, direction, or CCD that caused it and the date of CM's notice, and shall include a breakdown of labor hours and rates, materials, equipment, subcontractor pricing, markup, and Fee, and any claimed time impact in days."),
        ("1.03.B", "CP numbering. CPs are numbered in sequence (CP-0001, CP-0002, and so on). A revised CP keeps its number with a letter suffix (CP-0201A)."),
        ("1.04.A", "Backup. Every CP shall attach the RFI, ASI, or CCD that caused it, subcontractor quotes with their own line-item breakdowns, equipment logs, and T&M tags. A lump-sum subcontractor quote without a breakdown is not acceptable backup."),
        ("1.05.A", "Time-and-material tags. T&M tags shall list workers, hours, equipment, and materials for each day, and shall be signed by CM's superintendent and Owner's Representative and submitted within 3 business days after the work is performed. Tags signed only by a subcontractor's foreman are not accepted."),
        ("1.06.A", "CP log. CM shall keep the CP log required by Section 6.9 of the Agreement and submit it with each Application for Payment."),
    ]),
    ("02 82 00", "Asbestos Remediation", [
        ("1.01.A", "Summary. Removal and disposal of asbestos-containing materials (ACM) identified in Owner's hazardous materials survey, in the existing building areas shown on the abatement drawings."),
        ("1.03.A", "Hazardous materials survey. Owner's survey identifies ACM in Wing A floor tile, pipe insulation in Wing B, and gym roofing mastic. The survey did not identify mastic under flooring in classrooms 110 to 116. Quantities in the survey are for information; CM shall verify before abatement."),
        ("1.04.A", "Suspect materials not in the survey. If CM or the abatement contractor finds suspect material not identified in the survey, stop work in the area, isolate it, sample it, and notify Owner and Architect the same day. Notice of a differing condition is governed by Section 6.2(c) of the Agreement."),
        ("3.04.A", "Waste handling and disposal. The abatement contractor shall package ACM waste in labeled, sealed containers, transport it in an enclosed vehicle, and dispose of it at a licensed landfill. Waste manifests shall be submitted to Owner within 10 days of disposal."),
        ("3.06.A", "Restoration. Patching and painting of surfaces disturbed by abatement are not part of this Section; restoration is by the trade sections only where shown on the Drawings."),
    ]),
    ("07 62 00", "Sheet Metal Flashing and Trim", [
        ("1.01.A", "Summary. Parapet copings, counterflashings, through-wall flashings, and storefront and window head flashings."),
        ("2.01.A", "Material. Prefinished galvanized steel sheet, ASTM A653, G90 coating, with a two-coat fluoropolymer finish in the color selected by Architect."),
        ("2.02.A", "Copings. Form parapet copings from 24-gauge sheet with continuous cleats and concealed splice plates at joints."),
        ("2.02.B", "Counterflashings. Form counterflashings from 24-gauge sheet, set in reglets or surface-mounted with termination bar and sealant."),
        ("3.01.A", "Installation. Install flashing to SMACNA Architectural Sheet Metal Manual details, with expansion joints at 10 feet on center maximum and lapped, sealed joints."),
        ("3.02.A", "Head flashings. Provide head flashings with end dams and drip edges at every storefront and window opening, turned up behind the weather barrier at least 4 inches."),
    ]),
    ("08 71 00", "Door Hardware", [
        ("1.01.A", "Summary. Hardware for swinging doors, including hinges, locksets, exit devices, closers, stops, and seals, scheduled in hardware sets HW-1 through HW-9."),
        ("2.01.A", "Finish. Satin chrome, BHMA 626 (US26D), unless noted otherwise in the hardware sets."),
        ("2.03.A", "Hardware set HW-1 (classroom doors). Three butt hinges, classroom-function lockset, wall stop, and silencers."),
        ("2.03.B", "Hardware set HW-2 (corridor doors C101 to C108). Three butt hinges, passage latchset, overhead stop, and silencers. Standard, non-rated hardware."),
        ("2.03.C", "Hardware set HW-4 (corridor doors C201 to C212). Three butt hinges, passage latchset, surface closer with parallel arm, kick plate, and gasketing."),
        ("3.01.A", "Installation. Mount hardware at the heights in the DHI recommended locations. Adjust closers for opening force and closing speed to meet accessibility requirements."),
    ]),
    ("09 22 16", "Non-Structural Metal Framing", [
        ("1.04.A", "Submittals. Product data for studs and track, and a stud schedule showing gauge, spacing, and height for each partition type, with the manufacturer's limiting-height tables."),
        ("2.01.A", "Studs and track. ASTM C645 steel studs and track, G40 coating, 3-5/8 inch and 6 inch depths as shown."),
        ("2.01.B", "Gauge. 20-gauge (30 mil) studs are permitted for interior partitions up to 14 feet in height."),
        ("2.01.C", "Partitions over 14 feet. Gauge and spacing as indicated on the Drawings, at a deflection limit of L/240 under a 5 psf lateral load."),
        ("3.01.A", "Installation. Install studs at 16 inches on center unless shown otherwise, with deflection track at the top of partitions that run to structure."),
    ]),
    ("22 14 26", "Roof Drains", [
        ("1.01.A", "Summary. Primary roof drains, overflow roof drains, and their leaders to the building storm drain or to daylight."),
        ("2.01.A", "Primary roof drains. Cast iron body with flashing clamp, underdeck clamp, and cast iron dome, sized as shown on the plumbing drawings."),
        ("2.02.A", "Overflow roof drains. Provide where indicated on the Drawings, with a 2-inch water dam above the roof surface. Where none are indicated, none are required."),
        ("2.03.A", "Leaders. Service-weight cast iron no-hub pipe and fittings, 4-inch minimum, insulated where above occupied spaces."),
        ("3.01.A", "Installation. Set drains level at the low points of the roof, coordinated with the roofing installer, and test leaders to 10 feet of head for 15 minutes."),
        ("3.02.A", "Cleanouts. Provide a cleanout at the base of each vertical leader and at each change of direction greater than 45 degrees."),
    ]),
]
for num, title, paras in SPECS:
    add_doc("spec", f"Section {num}", f"Section {num} {title}", SPEC_DATE, "architect",
            {"division": num[:2], "spec_section": num, "issue": "Bid set"},
            [(p, b, SPEC_DATE, "architect") for p, b in paras])

# ---------------------------------------------------------------------------
# 3. RFIs  (num, asked, answered, q_party, originator, subject, spec_refs, dwg_refs,
#           question, suggestion, answer, asi, spec_cite)
# ---------------------------------------------------------------------------
RFIS = [
    ("RFI-104", "2020-02-05", "2020-02-12", "gc", "Example Builders", "Temporary power source",
     [], ["E-001"],
     "Drawing E-001 does not show where temporary construction power is to be taken from. Please confirm the point of connection for the site office and trailers.",
     "Take temporary power from the existing service at the Wing B electrical room, panel MDP-B, through a new 200 A fused disconnect.",
     "Answered in the Contract Documents. See Drawing E-001 general note 6: temporary power is from the existing service at the Wing B electrical room. CM's proposed connection is acceptable. Returned under Section 7.2.",
     None, None),
    ("RFI-109", "2020-02-24", "2020-03-02", "gc", "Northwest Door & Hardware", "Corridor door fire ratings C101 to C108",
     ["08 71 00"], ["A-101", "G-002"],
     "Life-safety plan G-002 shows a 1-hour rated corridor at C101 to C108, but the door schedule and hardware set HW-2 show non-rated doors and hardware. Please confirm the required rating.",
     "Provide 90-minute labeled door assemblies with fire-rated hardware in place of HW-2.",
     "Corridor doors C101 to C108 shall be 90-minute assemblies with fire-rated hardware. See ASI-014.",
     "ASI-014", ("Section 08 71 00", "2.03.B")),
    ("RFI-112", "2020-02-03", "2020-02-10", "gc", "Cascade Plumbing", "Gym roof overflow drains",
     ["22 14 26"], ["P-201"],
     "Drawing P-201 shows four primary roof drains at the gym roof and no overflow drains. The gym roof has parapets on all four sides, and the plumbing code requires secondary drainage. Please confirm whether overflow drains are required.",
     "Add two overflow roof drains next to primary drains RD-2 and RD-4, with 4-inch cast iron leaders discharging to daylight at the north wall.",
     "Provide two overflow roof drains as suggested, with 4-inch cast iron leaders to daylight at the north wall. See ASI-007 for revised Drawing P-201 and Section 22 14 26 paragraph 2.02.A.",
     "ASI-007", ("Section 22 14 26", "2.02.A")),
    ("RFI-118", "2020-02-18", "2020-02-25", "gc", "Example Builders", "Finish floor elevation at addition connector",
     [], ["A-100", "S-101"],
     "The finish floor elevation of the addition is not dimensioned where it meets the existing Wing A corridor. Survey shows the existing corridor at 100'-1 1/4\". Please confirm the addition elevation.",
     "Set the addition finish floor at 100'-1 1/4\" to match the existing corridor, with no transition strip.",
     "Match the existing corridor elevation of 100'-1 1/4\". No transition strip is required. No change to cost or time is intended.",
     None, None),
    ("RFI-124", "2020-03-04", "2020-03-13", "sub", "Summit Roofing", "Coping gauge at gym parapet",
     ["07 62 00"], ["A-520"],
     "Section 07 62 00 paragraph 2.02.A calls for 24-gauge copings, but detail 3/A-520 at the gym parapet shows a 20-inch-wide coping. 24-gauge will oil-can at that width. Please confirm the gauge.",
     "Use 22-gauge copings at parapets wider than 16 inches.",
     "Accepted. Use 22-gauge copings where the coping is wider than 16 inches. See ASI-019.",
     "ASI-019", ("Section 07 62 00", "2.02.A")),
    ("RFI-131", "2020-05-22", "2020-06-01", "gc", "Example Builders", "Corridor ceiling access panels",
     [], ["A-501"],
     "Reflected ceiling plan A-501 shows hard-lid gypsum ceilings in the existing corridors with no access panels. Valves, fire dampers, and VAV boxes above these ceilings need access. Please provide access panel locations.",
     "Provide 14 flush 24 x 24 inch access panels at the locations marked on attached sketch SK-131.",
     "Provide 14 flush, gypsum-board-faced access panels, 24 x 24 inches, at the locations on SK-131. Use fire-rated panels where the ceiling is part of a rated assembly.",
     None, None),
    ("RFI-137", "2020-04-20", "2020-04-27", "sub", "Brightline Painting", "Paint color for exposed structure in commons",
     [], ["A-700"],
     "The finish schedule on A-700 lists exposed structure in the commons but gives no color. Please confirm the color.",
     "Paint exposed structure P-3 to match the ceiling.",
     "Refer to the finish schedule on A-700, note 12: exposed structure is P-3. Answered in the Contract Documents.",
     None, None),
    ("RFI-140", "2020-07-06", "2020-07-13", "sub", "Cascade Plumbing", "Kitchen floor drains",
     [], ["P-301", "Q-101"],
     "Drawing P-301 shows two floor drains in the kitchen. Food service plan Q-101 shows a dish machine, a tilting kettle, and a walk-in cooler condensate line that each need an indirect drain. Please confirm the number and location of floor drains.",
     "Add three floor drains, at the dish machine, the tilting kettle, and the walk-in cooler.",
     "Provide three added floor drains at the dish machine, the tilting kettle, and the walk-in cooler, as suggested, connected to the grease waste line.",
     None, None),
    ("RFI-146", "2020-05-04", "2020-05-11", "sub", "Rainier Mechanical", "Library ceiling height and duct clearance",
     [], ["A-502", "M-202"],
     "In the Wing B library the existing beams leave 11 inches below the structure at the perimeter, and the supply duct shown on M-202 is 14 inches deep. Please advise.",
     "Lower the ceiling 4 inches at the library perimeter soffit.",
     "Lower the perimeter soffit 4 inches as suggested. The center ceiling stays at the height shown. No change to cost or time is intended.",
     None, None),
    ("RFI-152", "2020-09-04", "2020-09-14", "sub", "Evergreen Flooring", "Stair nosings at existing stairs",
     [], ["A-310"],
     "Section 09 65 13 calls for rubber stair nosings at both existing stairs. The existing concrete stair edges are worn and chipped up to 3/4 inch, and the rubber nosings will not bear on them. Please advise.",
     "Use aluminum abrasive nosings anchored into the concrete, with epoxy fill at the chipped edges.",
     "Change the nosings at both existing stairs to aluminum abrasive nosings anchored into the concrete, with epoxy fill at the chipped edges, as suggested.",
     None, None),
    ("RFI-158", "2020-09-14", "2020-09-21", "sub", "Summit Athletic Interiors", "Bleacher anchors at existing gym slab",
     [], ["S-310"],
     "Drawing S-310 shows wedge anchors for the telescoping bleachers. Cores taken in the existing gym slab tested at 2,500 psi, below the 4,000 psi assumed for the wedge anchor capacity. Please advise.",
     "Use adhesive (epoxy) anchors at the same spacing.",
     "Use epoxy adhesive anchors, 5/8 inch diameter with 5 inch embedment, at the spacing shown on S-310. Special inspection is required.",
     None, None),
    ("RFI-162", "2020-05-18", "2020-05-26", "gc", "Example Builders", "Vapor retarder under addition slab",
     [], ["S-101"],
     "Detail 1/S-101 shows a vapor retarder under the addition slab on grade but no thickness. Please confirm.",
     "Use a 15-mil vapor retarder with taped seams.",
     "Use a 15-mil vapor retarder meeting ASTM E1745 Class A, seams taped, as suggested. Answered in the general structural notes.",
     None, None),
    ("RFI-166", "2020-10-02", "2020-10-12", "sub", "Rainier Mechanical", "Rooftop unit curbs",
     [], ["M-501"],
     "Drawing M-501 shows the new rooftop units RTU-3 and RTU-4 set on the existing curbs. The scheduled units have a larger footprint than the existing curbs. Please advise.",
     "Provide manufactured curb adapters for RTU-3 and RTU-4.",
     "Provide manufactured curb adapters for RTU-3 and RTU-4. See ASI-034 for the revised detail on M-501.",
     "ASI-034", None),
    ("RFI-171", "2020-02-24", "2020-03-02", "sub", "Sentinel Fire Alarm", "Classroom fire alarm notification devices",
     [], ["FA-101"],
     "Drawing FA-101 shows horn-only notification devices in the classrooms. Classrooms are occupied spaces and require visible notification. Please confirm the device type.",
     "Replace classroom horns with horn/strobes, 75 cd minimum.",
     "Provide horn/strobe devices in all classrooms in place of the horns shown on FA-101.",
     None, None),
    ("RFI-175", "2020-03-16", "2020-03-23", "gc", "Northwest Door & Hardware", "Closers at corridor doors C201 to C212",
     ["08 71 00"], ["A-102"],
     "Please confirm whether closers are required at corridor doors C201 to C212.",
     "Provide surface closers at C201 to C212.",
     "Closers are required per HW-4.",
     None, ("Section 08 71 00", "2.03.C")),
    ("RFI-180", "2020-04-13", "2020-04-20", "sub", "Rainier Mechanical", "Kitchen hood location",
     [], ["M-401", "S-401"],
     "Drawing M-401 shows the kitchen exhaust hood on the east wall. The existing roof beam at that wall blocks the duct riser to the roof. Please advise.",
     "Relocate the hood to the south wall, where the riser can pass between beams.",
     "Relocate the kitchen hood to the south wall as suggested. Revised layout on sketch SK-180 attached.",
     None, None),
    ("RFI-183", "2020-06-15", "2020-06-22", "sub", "Cascade Plumbing", "Gas shutoff at science rooms",
     [], ["P-220"],
     "Drawing P-220 shows gas outlets at the lab benches in science rooms 201 and 203 but no room shutoff. The fire code requires an emergency shutoff for each lab room. Please advise.",
     "Add a solenoid emergency gas shutoff valve with a push-button station at the door of each room.",
     "Provide a solenoid emergency gas shutoff valve with a push-button station at the exit door of rooms 201 and 203, as suggested.",
     None, None),
    ("RFI-189", "2020-07-20", "2020-07-27", "gc", "Example Builders", "Elevator pit sump",
     [], ["A-130"],
     "The elevator pit on A-130 shows a sump but no pump or oil interceptor. Please confirm.",
     "Provide a sump with a duplex pump; no oil interceptor (machine-roomless traction elevator).",
     "Provide the sump with a single submersible pump discharging to the storm system. An oil interceptor is not required for the traction elevator.",
     None, None),
    ("RFI-196", "2020-08-17", "2020-08-24", "sub", "Northwest Door & Hardware", "Hardware finish at gym doors",
     ["08 71 00"], ["A-104"],
     "Gym door hardware sets do not state a finish. Please confirm.",
     "Use satin chrome, 626.",
     "Use satin chrome, BHMA 626, per Section 08 71 00 paragraph 2.01.A. Answered in the Contract Documents.",
     None, ("Section 08 71 00", "2.01.A")),
    ("RFI-205", "2020-06-12", "2020-06-19", "gc", "Example Builders", "Wing A casework and new data outlets",
     [], ["A-401", "T-101"],
     "Drawing A-401 places casework on the corridor walls of rooms 110 to 118, where T-101 shows the new data outlets and the MEP rough-in - Wing A is already routed. Please advise.",
     "Move the casework to the exterior walls of each room.",
     "Move the casework to the opposite (exterior) walls of rooms 110 to 118. See ASI-061.",
     "ASI-061", None),
    ("RFI-214", "2020-06-05", "2020-06-12", "sub", "Puget Steel Erectors", "Gym roof truss bearing at existing masonry wall",
     [], ["S-301"],
     "Detail 4/S-301 shows a standard bearing plate for the gym roof trusses at the existing masonry wall. The plate holes conflict with the existing wall's anchor layout found in the field. How should the trusses bear?",
     "Provide slotted bearing assemblies, field-welded after the trusses are set.",
     "Detail 4/S-301 is revised. Provide slotted bearing assemblies, field-welded after the trusses are set, with special inspection of the welds. See ASI-058.",
     "ASI-058", None),
    ("RFI-221", "2020-06-18", "2020-06-25", "sub", "Sentinel Fire Protection", "Sprinkler mains at addition corridor",
     [], ["FP-201", "M-201"],
     "The sprinkler mains on FP-201 run through the addition corridor ceiling space, where the revised duct mains on M-201 now sit. There is no room for both. Please advise.",
     "Reroute the sprinkler mains through the classrooms and add zones as needed.",
     "Reroute the mains around the duct mains and add two zones. See ASI-070.",
     "ASI-070", None),
    ("RFI-233", "2020-06-17", "2020-06-24", "sub", "Cascade Glazing", "Storefront head anchorage at addition",
     ["07 62 00"], ["A-501"],
     "Detail 7/A-501 anchors the storefront heads directly to the framing. The framing at the heads cannot take the storefront wind load without deflecting more than the storefront allows. Please advise.",
     "Add steel subframing above each storefront opening.",
     "Revised detail 7/A-501: provide steel subframing (HSS 4x4) above every storefront opening at the addition, with head flashing per Section 07 62 00 paragraph 3.02.A.",
     None, ("Section 07 62 00", "3.02.A")),
    ("RFI-240", "2020-09-21", "2020-09-28", "sub", "Cascade Plumbing", "Cleanouts at gym roof drain leaders",
     ["22 14 26"], ["P-201"],
     "Drawing P-201 does not show cleanouts on the new gym overflow leaders. Please confirm.",
     "Provide cleanouts at the base of each leader.",
     "Provide cleanouts at the base of each leader per Section 22 14 26 paragraph 3.02.A. Answered in the Contract Documents.",
     None, ("Section 22 14 26", "3.02.A")),
]

for (num, asked, answered, qp, orig, subj, specs, dwgs, q, sug, ans, asi, cite) in RFIS:
    assert d(asked) <= d(answered) and (d(answered) - d(asked)).days <= 10, num
    returned = "Answered in the Contract Documents" in ans
    add_doc("rfi", num, f"{num} {subj}", asked, "gc",
            {"status": "answered", "asked_on": asked, "answered_on": answered,
             "needed_by": add_days(asked, 7), "originator": orig, "spec_refs": specs, "drawing_refs": dwgs,
             "critical_path": False, "returned_as_answered_in_documents": returned,
             "answer_refers_to": asi},
            [("Question", q, asked, qp), ("Suggested solution", sug, asked, qp), ("Answer", ans, answered, "architect")])
    if cite:
        link(num, cite[0], "cites", f"{num} asks about {cite[0]} paragraph {cite[1]}.", "Question", cite[1])

# ---------------------------------------------------------------------------
# 4. ASIs  (num, date, title, description, affected, supersedes)
# ---------------------------------------------------------------------------
ASIS = [
    ("ASI-007", "2020-02-10", "Gym roof overflow drains",
     "Add two overflow roof drains at the gym roof next to primary drains RD-2 and RD-4, with 2-inch water dams and 4-inch cast iron leaders to daylight at the north wall, per the response to RFI-112.",
     "Drawing P-201 (revised, cloud 1). Section 22 14 26 paragraph 2.02.A: overflow roof drains are now indicated at the gym roof.",
     [("Section 22 14 26", "2.02.A")]),
    ("ASI-014", "2020-03-02", "Corridor doors C101 to C108 fire rating",
     "Corridor doors C101 to C108 are revised to 90-minute labeled assemblies. Replace hardware set HW-2 at these doors with new set HW-2R: three ball-bearing hinges, fire-rated latchset, surface closer, and positive-pressure gasketing.",
     "Door schedule on A-101 (revised). Section 08 71 00 paragraph 2.03.B (HW-2 replaced by HW-2R at C101 to C108).",
     [("Section 08 71 00", "2.03.B")]),
    ("ASI-019", "2020-03-13", "Coping gauge at wide parapets",
     "Where a parapet coping is wider than 16 inches, form it from 22-gauge sheet in place of 24-gauge, per the response to RFI-124.",
     "Detail 3/A-520. Section 07 62 00 paragraph 2.02.A.",
     [("Section 07 62 00", "2.02.A")]),
    ("ASI-022", "2020-07-06", "Sprinkler heads at stage rigging",
     "Add upright sprinkler heads above the stage rigging grid, on a new branch line from the stage main, and revise the hydraulic calculation for the stage area.",
     "Drawing FP-102 (revised). Fire marshal permit revision required.",
     []),
    ("ASI-031", "2020-09-08", "Science room casework revisions",
     "Revise casework in science rooms 201 and 203: add one accessible-height work section (34 inches) with knee space in each room, and change the tall storage units to chemical-resistant tops.",
     "Drawing A-601 (revised elevations 2 and 5).",
     []),
    ("ASI-034", "2020-10-12", "Rooftop unit curb adapters",
     "Provide manufactured curb adapters for RTU-3 and RTU-4 to fit the scheduled units on the existing curbs, per the response to RFI-166.",
     "Drawing M-501 (revised detail 3).",
     []),
    ("ASI-036", "2020-10-19", "Classroom sinks in rooms 105 and 107",
     "Add a single-compartment stainless steel sink with gooseneck faucet in classrooms 105 and 107, with in-wall blocking, supply, and waste.",
     "Drawing P-210 (revised). Drawing A-401 (casework elevation 4).",
     []),
    ("ASI-040", "2020-04-13", "Seismic bracing of mechanical and electrical systems",
     "Following the building official's plan review comments, provide seismic bracing for ductwork, piping, conduit racks, and suspended equipment throughout the building, designed by the installing trades' engineers.",
     "Drawings M-001 and E-001 (new general notes). Structural general notes S-001.",
     []),
    ("ASI-044", "2020-05-18", "Restroom 140 partitions",
     "Add two toilet partitions in restroom 140 to match the existing six, for a total of eight compartments.",
     "Drawing A-120 (revised enlarged plan).",
     []),
    ("ASI-047", "2020-07-06", "Whiteboards in rooms 210 to 213",
     "Replace the tackboards shown in rooms 210 to 213 with 4 x 12 foot porcelain-steel whiteboards with map rail.",
     "Drawing A-301 (revised interior elevations).",
     []),
    ("ASI-050", "2020-07-20", "Patch and paint after abatement",
     "Patch and paint walls opened or damaged during abatement in Wing A and Wing B, to match adjacent finishes, using the paint system in Section 09 91 23 for new gypsum board.",
     "Section 02 82 00 paragraph 3.06.A (restoration is now included where abatement opened walls). Section 09 91 23.",
     [("Section 02 82 00", "3.06.A")]),
    ("ASI-058", "2020-06-12", "Gym truss bearing assemblies",
     "Revise detail 4/S-301: provide slotted bearing assemblies at each gym roof truss bearing on the existing masonry wall, field-welded after the trusses are set, with special inspection of welds.",
     "Drawing S-301 (revised detail 4).",
     []),
    ("ASI-061", "2020-06-19", "Wing A casework relocation",
     "Relocate casework in rooms 110 to 118 from the corridor walls to the exterior walls. Provide new in-wall blocking at the new locations and patch the abandoned blocking locations.",
     "Drawing A-401 (revised plans and elevations).",
     []),
    ("ASI-070", "2020-06-25", "Sprinkler main reroute at addition",
     "Reroute the addition sprinkler mains around the revised duct mains, through the classroom ceiling spaces, and add two zones with zone control valves.",
     "Drawing FP-201 (revised). Hydraulic calculations to be resubmitted.",
     []),
    ("ASI-075", "2020-06-30", "Sunshades at existing south windows",
     "Add aluminum horizontal sunshades above the south-facing replacement windows of the existing building, anchored through the new head flashing.",
     "Drawing A-210 (revised south elevation). Section 07 62 00 head flashing coordination.",
     []),
]
for num, date, title, desc, affected, supersedes in ASIS:
    add_doc("asi", num, f"{num} {title}", date, "architect",
            {"issued_on": date, "states_no_change_in_cost_or_time": True},
            [("Description", desc, date, "architect"),
             ("Drawings/specs affected", affected, date, "architect"),
             ("Issued by", f"Issued by {ARCH} on {date}. This ASI is not intended to change the Contract Sum or Contract Time (Section 6.8). If CM believes it does, CM shall give notice under Section 6.2(a) before proceeding.", date, "architect")])
    for spec, para in supersedes:
        link(num, spec, "supersedes", f"{num} replaces {spec} paragraph {para}.", "Description", para)

for (num, asked, answered, *_rest) in RFIS:
    asi = _rest[-2]
    if asi:
        assert DOC_BY_KEY[asi]["issued_on"] == answered, (num, asi)
        link(num, asi, "answered_by", f"The answer to {num} refers to {asi}, issued the same day.", "Answer", None)

# ---------------------------------------------------------------------------
# 5. Submittals (num, title, sub, submitted, returned, action, comments, spec cite, asi cite)
# ---------------------------------------------------------------------------
SUBMITTALS = [
    ("02 82 00-01", "Abatement work plan", "Clearwater Abatement", "2020-02-07", "2020-02-14", "No exceptions taken",
     "Work plan, containment drawings, air monitoring plan, and landfill acceptance letter reviewed. No exceptions taken.",
     ("Section 02 82 00", "3.04.A"), None),
    ("22 14 26-01", "Roof drains product data", "Cascade Plumbing", "2020-02-24", "2020-03-06", "Approved as noted",
     "Primary drains acceptable. Add overflow drain bodies with 2-inch water dams at the gym roof per ASI-007.",
     ("Section 22 14 26", "2.02.A"), "ASI-007"),
    ("08 41 13-01", "Aluminum storefront shop drawings", "Cascade Glazing", "2020-03-02", "2020-03-16", "Rejected",
     "Submitted framing system is not thermally broken and does not meet the specified U-factor. Submit the specified system or a substitution request under Division 01.",
     None, None),
    ("08 71 00-01", "Door hardware schedule", "Northwest Door & Hardware", "2020-03-09", "2020-03-23", "Revise and resubmit",
     "Revise the sets at corridor doors C101 to C108 to HW-2R, fire-rated, per ASI-014. Confirm closers at C201 to C212 as listed in HW-4.",
     ("Section 08 71 00", "2.03.B"), "ASI-014"),
    ("05 12 00-01", "Structural steel shop drawings", "Puget Steel Erectors", "2020-03-19", "2020-04-02", "Approved as noted",
     "Approved as noted. Field-verify the existing masonry wall anchor layout at the gym truss bearings before fabricating bearing plates.",
     None, None),
    ("09 22 16-01", "Metal stud framing product data and stud schedule", "Evergreen Framing", "2020-04-06", "2020-04-20", "Revise and resubmit",
     "Stud schedule is incomplete: limiting-height tables are missing for the gym walls. Resubmit with the full schedule.",
     ("Section 09 22 16", "1.04.A"), None),
    ("07 54 23-01", "TPO roofing product data and warranty", "Summit Roofing", "2020-04-13", "2020-04-27", "No exceptions taken",
     "Membrane, insulation, and 20-year warranty form reviewed. No exceptions taken.",
     None, None),
    ("09 65 19-01", "Resilient tile flooring (VCT) product data and samples", "Northwest Floors", "2020-04-27", "2020-05-08", "No exceptions taken",
     "VCT colors selected per finish schedule. No exceptions taken.",
     None, None),
    ("09 22 16-02", "Metal stud framing resubmittal", "Evergreen Framing", "2020-05-01", "2020-05-11", "Approved as noted",
     "Approved as noted. At the gym walls (gridlines G1 to G6), provide 18-gauge (43 mil) studs in place of the 20-gauge shown in the stud schedule. Other partitions approved as submitted.",
     ("Section 09 22 16", "2.01.B"), None),
    ("09 65 19-02", "Rubber tile flooring resubmittal (Owner change)", "Northwest Floors", "2020-07-08", "2020-07-20", "No exceptions taken",
     "Rubber tile in classrooms 201 to 212 per Owner's direction of 2020-06-29. Lead time stated by the supplier: 6 weeks. No exceptions taken.",
     None, None),
]
for num, title, sub, sub_on, ret_on, action, comments, spec_cite, asi_cite in SUBMITTALS:
    assert d(sub_on) < d(ret_on)
    add_doc("submittal", num, f"Submittal {num} {title}", sub_on, "gc",
            {"spec_section": num.split("-")[0], "sequence": num.split("-")[1], "subcontractor": sub,
             "submitted_on": sub_on, "returned_on": ret_on, "action": action},
            [("Item", f"{title}, prepared by {sub}, reviewed and stamped by CM, submitted to Architect {sub_on}.", sub_on, "sub"),
             ("Action", f"{action}. Returned {ret_on}.", ret_on, "architect"),
             ("Reviewer comments", comments, ret_on, "architect")])
    if spec_cite:
        link(num, spec_cite[0], "cites", f"Submittal {num} is reviewed against {spec_cite[0]} paragraph {spec_cite[1]}.", "Reviewer comments", spec_cite[1])
    if asi_cite:
        link(num, asi_cite, "cites", f"Reviewer comments on {num} apply {asi_cite}.", "Reviewer comments", None)

# ---------------------------------------------------------------------------
# 6. Correspondence that cases cite (kind "other"): owner emails/letters, field
#    order, letters, permit. One document per message; several directions in
#    one email become separate pieces.
# ---------------------------------------------------------------------------
OWNER_DIRECTIONS = {
    "CP-0203": "Please add 24 data drops in the library, in addition to the 12 shown on T-101. Locations per the librarian's markup attached. Send pricing before you proceed.",
    "CP-0204": "The District has decided to delete the covered walkway canopy at the bus loop shown on S-401. Please stop canopy fabrication and send a credit.",
    "CP-0210": "Please provide blocking and power for 16 classroom smartboards. Locations per the District technology standard attached.",
    "CP-0211": "Please add four pole lights at the staff parking lot, matching the site fixtures on E-100. Price before proceeding.",
    "CP-0213": "Please add wall padding on the east and west gym walls to match the north wall padding in Section 11 66 23.",
    "CP-0220": "Please add solar control window film at the south classrooms. Product per the attached cut sheet.",
    "CP-0221": "Please add duplex outlets in the corridors at 20-foot spacing, between the outlets shown on E-201. OK to proceed on T&M with daily tags.",
    "CP-0230": "Please add acoustic wall panels in the gym. The District's acoustic consultant recommends panels on the upper half of the east and west walls.",
    "CP-0232": "Please move the locker room benches from the north wall to the center of each locker room, per the coach's request.",
    "CP-0234": "Please add four high-volume, low-speed ceiling fans in the gym. Structural support to be confirmed by the fan supplier's engineer.",
    "CP-0236": "Please add four hose bibbs at the courtyard, two more than shown on P-102. OK to proceed on T&M.",
    "CP-0401": "The District will provide a hydraulic stage lift in the addition multipurpose room. Please provide the lift pit with the addition foundations. Lift supplier's pit drawing attached.",
    "CP-0403": "Please add fabric-wrapped acoustic wall panels and wall blocking in music room 205 and band room 206, full height to the deck.",
    "CP-0404": "Please add a second play structure with safety surfacing at the primary playground. Equipment selection attached.",
    "CP-0406": "The District wants the addition roof to be PV-ready: add blocking, conduit sleeves, and insulation to R-38 under the membrane. Solar array itself is by others later.",
    "CP-0413": "Please change the addition classroom flooring from VCT to rubber tile in classrooms 201 to 212. Product per the attached selection.",
    "CP-0415": "Please add 16 data drops in the Wing B administration offices, locations per the attached markup.",
}
CORR = {}   # doc key -> dict(kind label, date, party, title, pieces list of (section, body, cp))
CAUSE_SECTION = {}  # cp -> (key, section)
for c, src in CASES:
    ref = c["cause"]["reference"]
    m = re.match(r"^Owner (email|letter) (\d{4}-\d\d-\d\d)$", ref)
    if m:
        kind_label, date = m.group(1), m.group(2)
        key = ("OE-" if kind_label == "email" else "OL-") + date
        entry = CORR.setdefault(key, {"label": f"Owner's Representative {kind_label}", "date": date, "party": "owner",
                                      "cited_as": ref, "items": []})
        entry["items"].append(c["id"])
for key in sorted(CORR):
    e = CORR[key]
    items = sorted(e["items"])
    pieces = []
    for n, cp in enumerate(items, 1):
        sec = f"Direction {n}"
        pieces.append((sec, OWNER_DIRECTIONS[cp], e["date"], "owner"))
        CAUSE_SECTION[cp] = (key, sec)
    pieces.append(("Signature", f"{OWNER_REP}. Sent through the project management platform designated by Owner (Section 14.2).", e["date"], "owner"))
    title = f"{e['label']}, {e['date']}" + (f" ({len(items)} directions)" if len(items) > 1 else "")
    add_doc("other", key, title, e["date"], "owner",
            {"subkind": "owner_" + e["label"].split()[-1], "cited_as": e["cited_as"]}, pieces)

OTHER_DOCS = [
    ("FO-07", "Architect field order FO-07: emergency generator pad", "2020-06-15", "architect", "architect_field_order",
     "Architect field order FO-07",
     [("Direction", "Provide a 4-inch reinforced concrete pad, 6 x 10 feet, under the emergency generator shown on grade on E-001, set 2 inches above finished grade."),
      ("Basis", "Generator manufacturer's installation requirements. Field order issued under Section 6.1; CM to advise of any cost or time under Section 6.2(b).")]),
    ("NL-09", "CM notice letter NL-09: weather delay to roofing", "2020-11-24", "gc", "cm_notice_letter",
     "Notice letter NL-09",
     [("Notice", "CM gives notice under Section 6.2(d) of a delay to Roofing - addition caused by sustained rain and wind on 2020-11-06, 2020-11-09, 2020-11-10, 2020-11-12, 2020-11-13 and 2020-11-16. The roofing crew could not install membrane on those days; see daily reports for those dates."),
      ("Preliminary estimate", "6 days of time and extended general conditions. A Change Proposal will follow within 21 days.")]),
    ("LTR-ERECTOR-2020-06-10", "Steel erector letter, 2020-06-10: crane availability", "2020-06-10", "sub", "subcontractor_letter",
     "Erector letter 2020-06-10",
     [("Letter", "Puget Steel Erectors advises that its crawler crane is committed to another project and will arrive at the site 5 working days later than planned for Erect structural steel - addition. We request the schedule be adjusted and will submit standby costs."),
      ("Signature", "Project manager, Puget Steel Erectors.")]),
    ("LTR-FLATWORK-2020-06-15", "Flatwork subcontractor letter, 2020-06-15: crew shortage", "2020-06-15", "sub", "subcontractor_letter",
     "Sub letter 2020-06-15",
     [("Letter", "Due to a crew shortage, we will start Curbs, sidewalks and flatwork 8 working days later than the subcontract schedule, which calls for flatwork to follow site electrical directly."),
      ("Signature", "Operations manager, Cornerstone Flatwork.")]),
    ("PERMIT-2020-01-18", "Building permit issued (owner-held permit)", "2020-01-18", "owner", "permit_record",
     "City permit issued late (owner-held permit)",
     [("Permit record", "The city issued the building permit for the School Modernization and Addition on 2020-01-18. Owner applied for and holds the permit."),
      ("Schedule effect", "The baseline schedule submitted with the GMP showed mobilization on 2020-01-06, which depended on the permit. The permit arrived 12 days after that date; the Notice to Proceed was then issued for 2020-02-03.")]),
]
for key, title, date, party, subkind, cited, pcs in OTHER_DOCS:
    add_doc("other", key, title, date, party, {"subkind": subkind, "cited_as": cited},
            [(s, b, date, party) for s, b in pcs])

# ---------------------------------------------------------------------------
# 7. Field reports (kind daily_report) for concealed conditions
# ---------------------------------------------------------------------------
FIELD_REPORTS = [
    ("FR-12", "2020-02-03", "Soft organic soils at gym footing F-12",
     [("Observation", "Test pit at gym footing F-12 found soft, dark organic silt from 3 to 6 feet below grade. The geotechnical report assumed medium-dense sand at footing depth."),
      ("Action taken", "Excavation at F-12 stopped before the condition was disturbed further. Geotechnical engineer called to site; Owner's Representative and Architect notified by email the same day under Section 6.2(c)."),
      ("Photos", "Photos FR12-01 to FR12-06 of the test pit and spoil, with tape measure for scale.")]),
    ("FR-33", "2020-08-10", "Asbestos mastic under classroom flooring",
     [("Observation", "While removing the remaining floor finishes in classrooms 110 to 116 for MEP rough-in - Wing A, the crew exposed black mastic under a second layer of floor tile. Samples sent for analysis; lab reported 5% chrysotile the same afternoon. The hazardous materials survey did not identify mastic in these rooms."),
      ("Action taken", "Work stopped in classrooms 110 to 116, area isolated and posted. Owner's Representative and Architect notified the same day. Clearwater Abatement asked to mobilize 2020-08-11."),
      ("Photos", "Photos FR33-01 to FR33-09; lab report attached.")]),
    ("FR-41", "2020-10-05", "Abandoned concrete vault on storm line route",
     [("Observation", "Excavation for the storm line to the playfield hit an abandoned concrete vault, about 6 x 8 feet and 7 feet deep, directly on the line route. Civil drawing C-201 shows no structures along this route."),
      ("Action taken", "Excavation stopped at the vault. Owner's Representative and Architect notified the same day; civil engineer asked for a reroute. CM's excavator on standby."),
      ("Photos", "Photos FR41-01 to FR41-05.")]),
]
for key, date, title, pcs in FIELD_REPORTS:
    add_doc("daily_report", key, f"Field report {key}: {title}", date, "gc",
            {"subkind": "field_report", "report_date": date, "author": CM_SUPT},
            [(s, b, date, "gc") for s, b in pcs])

# ---------------------------------------------------------------------------
# 8. Schedule (one document, one piece per activity)
# ---------------------------------------------------------------------------
sched_pieces = []
for a in SCHED["activities"]:
    r = SCHED_CSV[a["id"]]
    dur = a["duration"]
    dur_txt = "milestone" if dur == 0 else f"{dur} working days"
    if a["actual_finish"]:
        status = f"complete, actual {a['actual_start']} to {a['actual_finish']}"
    elif a["actual_start"]:
        status = f"in progress, started {a['actual_start']}, {a['remaining']} working days remaining"
    else:
        status = "not started"
    preds = r["Predecessors"] or "none"
    body = (f"{a['id']} {a['name']}, {dur_txt}, WBS {a['wbs']}. Forecast {r['Start']} to {r['Finish']}. "
            f"Predecessors: {preds}. Status at data date: {status}.")
    if a.get("constraint"):
        body += f" Constraint: {a['constraint']['type']} {a['constraint']['date']}."
    sched_pieces.append((a["id"], body, r["Start"] or SPAN_START, "gc"))
add_doc("schedule", "SCH-2020-06-01", "Schedule update, data date 2020-06-01", SCHED["data_date"], "gc",
        {"file": "demo4/data/schedule.json", "data_date": SCHED["data_date"], "start": SCHED["start"],
         "forecast_substantial_completion": SCHED_CSV["A1090"]["Finish"], "activities": len(SCHED["activities"]),
         "relationships": len(SCHED["relationships"]), "also": ["demo4/data/schedule.xer", "demo4/data/schedule.xml", "demo4/data/schedule.csv"]},
        sched_pieces)

# ---------------------------------------------------------------------------
# 9. Daily reports
# ---------------------------------------------------------------------------
FIRM_BY_KEYWORD = [
    ("Abatement", "Clearwater Abatement"), ("demolition", "Northline Demolition"), ("Demolish", "Northline Demolition"),
    ("Haul-off", "Northline Demolition"), ("Excavation", "Granite Earthworks"), ("Underslab", "Granite Earthworks"),
    ("Site utilities", "Granite Earthworks"), ("Footings", "Granite Concrete"), ("Slab", "Granite Concrete"),
    ("structural steel", "Puget Steel Erectors"), ("Metal deck", "Puget Steel Erectors"), ("Seismic upgrade", "Example Builders (self-perform)"),
    ("Roofing", "Summit Roofing"), ("Reroof", "Summit Roofing"), ("Window", "Cascade Glazing"), ("storefront", "Cascade Glazing"),
    ("Exterior framing", "Evergreen Framing"), ("cladding", "Evergreen Framing"), ("Exterior painting", "Brightline Painting"),
    ("Fire sprinkler", "Sentinel Fire Protection"), ("MEP rough-in", "Rainier Mechanical, Sound Electric, Cascade Plumbing"),
    ("switchgear", "Sound Electric"), ("rooftop units", "Rainier Mechanical"), ("Energize", "Sound Electric"),
    ("Framing and drywall", "Evergreen Framing"), ("Ceilings", "Evergreen Framing"), ("Painting", "Brightline Painting"),
    ("Flooring", "Northwest Floors"), ("Gym wood floor", "Northwest Floors"), ("Casework", "Timberline Casework"),
    ("MEP trim", "Rainier Mechanical, Sound Electric, Cascade Plumbing"), ("Doors", "Northwest Door & Hardware"),
    ("Gym equipment", "Summit Athletic Interiors"), ("signage", "Pacific Specialties"), ("Elevator", "Pacific Vertical"),
    ("electrical and lighting", "Sound Electric"), ("paving", "Cornerstone Paving"), ("Curbs", "Cornerstone Flatwork"),
    ("Playground", "Evergreen Site Works"), ("Landscaping", "Evergreen Site Works"), ("fencing", "Evergreen Site Works"),
    ("Striping", "Cornerstone Paving"), ("Test and balance", "Rainier Mechanical"), ("Fire alarm", "Sentinel Fire Protection"),
    ("Functional", "Northwest Commissioning Group"), ("water testing", "Northwest Commissioning Group"),
]
PROGRESS = ["work continued on plan", "about half complete", "crew moved to the next area", "progress on schedule",
            "in progress, no issues", "nearing completion", "under way"]


def firm_for(name):
    for kw, firm in FIRM_BY_KEYWORD:
        if kw.lower() in name.lower():
            return firm
    return "Example Builders (self-perform)"


# Procurement and shop-drawing activities happen off site; daily reports skip them.
OFFSITE = {"A1130", "A1440", "A1450", "A1500", "A1600"}


def active_on(date):
    out = []
    for a in SCHED["activities"]:
        if a["duration"] == 0 or a["id"] in OFFSITE:
            continue
        r = SCHED_CSV[a["id"]]
        s, f = r["Start"], r["Finish"]
        if a["actual_finish"]:
            s, f = a["actual_start"], a["actual_finish"]
        if s and f and s <= date <= f:
            out.append(a["id"])
    return out


WEATHER_BAND = {1: (38, 47), 2: (39, 50), 3: (41, 55), 4: (44, 60), 5: (49, 66), 6: (53, 71), 7: (57, 77),
                8: (57, 77), 9: (52, 71), 10: (46, 60), 11: (41, 51), 12: (37, 46)}


def weather_default(date):
    lo, hi = WEATHER_BAND[d(date).month]
    lo += RNG.randint(-2, 2)
    hi += RNG.randint(-2, 3)
    sky = RNG.choice(["Overcast, dry", "Partly cloudy, dry", "Cloudy, light drizzle in the morning, no lost time", "Clear, dry"])
    if d(date).month in (6, 7, 8, 9):
        sky = RNG.choice(["Clear, dry", "Partly cloudy, dry", "Sunny, dry"])
    return f"{sky}. Low {lo} F, high {hi} F. No weather delay."


# Overrides: date -> dict(weather, work (list of (activity id, text)), issues, visitors, evidence [(cp, note)])
DR = {
    "2020-02-03": dict(work=[("A1000", "Notice to Proceed issued; preconstruction meeting held at the site office"),
                             ("A1100", "site office trailer delivered and set"),
                             ("A1130", "submittal schedule started")],
                       issues="Building permit posted at the site office (issued 2020-01-18). Test pit at gym footing F-12 found soft organic soils; see field report FR-12. Excavation at F-12 stopped; Owner's Representative and Architect notified.",
                       visitors="Owner's Representative; Architect; geotechnical engineer (afternoon, at F-12).",
                       evidence=[("CP-0225", "Day the soft soils at F-12 were found and reported."),
                                 ("CP-0224", "Permit posted; work started on the Notice to Proceed date.")]),
    "2020-02-04": dict(issues="Geotechnical engineer recommends over-excavating F-12 to firm native soil and replacing with structural fill; written recommendation to follow. No other delays.",
                       evidence=[("CP-0225", "Geotechnical recommendation for the soft soils at F-12.")]),
    "2020-03-04": dict(issues="Sentinel Fire Alarm began layout and wire pulls for added classroom horn/strobes following the RFI-171 response of 2020-03-02.",
                       evidence=[("CP-0222", "First day of work on the RFI-171 strobes.")]),
    "2020-05-11": dict(issues="Framing submittal 09 22 16-02 returned Approved as Noted: 18-gauge studs required at the gym walls. Comment forwarded to Evergreen Framing the same day (Section 8.3).",
                       evidence=[("CP-0205", "Submittal return received and distributed.")]),
    "2020-06-01": dict(issues="RFI-131 answered: 14 corridor access panels. Response sent to Evergreen Framing. Schedule update with data date 2020-06-01 issued."),
    "2020-06-03": dict(weather="Heavy rain, 1.42 in. recorded at the site gauge. Low 51 F, high 58 F. Work stopped at 10:30.",
                       work=[("A1340", "haul-off stopped at 10:30 when the addition footprint flooded")],
                       issues="Rain flooded the addition footprint. Trash pump set at the low corner; laborers on erosion control. Excavation and shoring - addition cannot start until the footprint is dry.",
                       evidence=[]),
    "2020-06-04": dict(weather="Rain, 0.96 in. Low 52 F, high 57 F. Site standing water most of the day.",
                       work=[("A1340", "no haul-off; footprint under water")],
                       issues="Pumping the addition footprint all day. No earthwork possible.", evidence=[]),
    "2020-06-05": dict(weather="Heavy rain, 1.18 in. Low 50 F, high 56 F.",
                       work=[("A1340", "completed last loads from the dry end of the footprint in the afternoon")],
                       issues="Addition footprint still flooded. Excavation and shoring - addition was planned to start today and did not.", evidence=[]),
    "2020-06-08": dict(weather="Rain, 0.88 in. Low 52 F, high 59 F.",
                       work=[],
                       issues="Fourth rain day. Pumping continued; footprint not workable. Owner's Representative walked the site and discussed the stage lift pit in the multipurpose room (Owner email of today).",
                       visitors="Owner's Representative (site walk, 13:00).",
                       evidence=[("CP-0401", "Owner's Representative discussed the stage lift pit on site the day of the direction.")]),
    "2020-06-09": dict(weather="Clearing, showers early. Low 50 F, high 63 F.",
                       issues="Footprint pumped down by noon; Granite Earthworks moved in and began excavation in the afternoon. CM preparing notice for the rain days of 2020-06-03 to 2020-06-08.",
                       evidence=[("CP-0411", "Recovery day after the rain; records pumping and the late start of excavation.")]),
    "2020-06-10": dict(issues="Puget Steel Erectors letter received: crawler crane committed elsewhere and arriving 5 working days late for Erect structural steel - addition.",
                       evidence=[("CP-0409", "Day the erector's crane letter was received.")]),
    "2020-06-11": dict(issues="T&M: Evergreen Framing installed access panels in the existing corridors per RFI-131. Tag 131-03 signed by the CM superintendent and the Owner's Representative.",
                       evidence=[("CP-0206", "T&M tag for RFI-131 access panels, signed by both parties.")]),
    "2020-06-15": dict(issues="Cornerstone Flatwork letter received: crew shortage, curbs and sidewalks to start 8 working days late. Architect issued field order FO-07 for a generator pad.",
                       evidence=[("CP-0410", "Day the flatwork crew-shortage letter was received."),
                                 ("CP-0207", "Field order FO-07 received.")]),
    "2020-06-22": dict(issues="CM crew formed and poured the generator pad per FO-07: 1 laborer and 1 finisher, 8 hours each; CM-owned skid steer 4 hours (equipment log attached).",
                       evidence=[("CP-0207", "Labor and skid steer hours for the FO-07 generator pad.")]),
    "2020-06-26": dict(weather="Thunderstorm, 1.61 in. in 3 hours. Low 58 F, high 66 F. Work stopped at 13:00.",
                       work=[("A1410", "storm sewer and domestic water laid in the open trench before the storm")],
                       issues="Storm flooded the open underslab utility trench at the addition. Bedding washed out over about 140 feet. Pumps set; trench barricaded.",
                       evidence=[]),
    "2020-06-29": dict(weather="Rain, 0.71 in. Low 55 F, high 63 F.",
                       work=[("A1410", "dewatering the trench; no pipe laid")],
                       issues="Trench still holding water. Bedding to be removed and replaced once dry. Owner email received today changing addition classroom flooring to rubber tile and moving locker room benches.",
                       evidence=[("CP-0413", "Owner flooring change received.")]),
    "2020-06-30": dict(weather="Showers, 0.38 in. Low 54 F, high 64 F.",
                       work=[("A1410", "re-excavating the trench at the east end; removed saturated bedding")],
                       issues="Second day of trench recovery. Mini excavator (CM-owned) 8 hours; 2 laborers on dewatering and bedding.",
                       evidence=[]),
    "2020-08-04": dict(issues="T&M: Cascade Plumbing installed 4 added hose bibbs at the courtyard. Tags signed by Cascade's foreman; CM superintendent and Owner's Representative did not sign.",
                       evidence=[("CP-0236", "Records the T&M work and who signed the tags.")]),
    "2020-08-10": dict(issues="Asbestos-containing black mastic found under a second layer of floor tile in classrooms 110 to 116 during floor removal for MEP rough-in - Wing A; see field report FR-33. Work stopped in those rooms; Owner's Representative and Architect notified today.",
                       evidence=[("CP-0212", "Day the concealed asbestos mastic was found.")]),
    "2020-08-11": dict(issues="Clearwater Abatement mobilized to classrooms 110 to 116 and set containment. Two added 30-yard dumpsters ordered for non-ACM demolition debris from the rooms; ACM waste handled by the abatement sub.",
                       visitors="Owner's Representative; abatement consultant (air monitoring).",
                       evidence=[("CP-0212", "Abatement mobilization and the added dumpsters.")]),
    "2020-10-05": dict(issues="Storm line excavation to the playfield hit an abandoned concrete vault on the line route; see field report FR-41. Excavation stopped; civil engineer asked for a reroute.",
                       evidence=[("CP-0217", "Day the abandoned vault was found.")]),
    "2020-10-06": dict(issues="Rerouted storm line around the vault per the civil engineer's sketch. CM-owned excavator 7 hours with operator and 1 laborer (equipment log attached).",
                       evidence=[("CP-0217", "Excavator and crew hours for the reroute.")]),
    "2020-11-18": dict(issues="T&M: Sound Electric installed added corridor outlets (third day). Tag 3 of 3 signed by the CM superintendent only; Owner's Representative not on site. Tag 2 also unsigned by the Owner's Representative.",
                       evidence=[("CP-0221", "Records the corridor-outlet T&M tags and missing Owner signatures.")]),
}
NOV_WEATHER = {
    "2020-11-06": "Rain 0.84 in., wind gusts to 34 mph. Low 42 F, high 49 F.",
    "2020-11-09": "Rain 0.61 in., wind gusts to 31 mph. Low 40 F, high 47 F.",
    "2020-11-10": "Rain 1.03 in. Low 41 F, high 46 F.",
    "2020-11-12": "Rain 0.55 in., gusts to 38 mph. Low 39 F, high 46 F.",
    "2020-11-13": "Rain 0.72 in. Low 40 F, high 48 F.",
    "2020-11-16": "Rain 0.93 in., gusts to 36 mph. Low 41 F, high 47 F.",
}
for date, w in NOV_WEATHER.items():
    DR[date] = dict(weather=w + " Roofing stood down.",
                    issues="Roofing - addition: membrane installation not possible in rain and wind; Summit Roofing crew sent home at 08:00. Other trades worked inside.",
                    evidence=[("CP-0227", "Weather day for the roofing delay.")])
EXTRA_DATES = ["2020-02-12", "2020-02-24", "2020-03-19", "2020-04-13", "2020-04-29", "2020-05-27", "2020-06-02",
               "2020-06-25", "2020-07-21", "2020-09-08", "2021-01-21", "2021-03-15", "2021-05-03", "2021-06-15", "2021-07-02"]
DR_DATES = sorted(set(DR) | set(EXTRA_DATES))
VISITORS = ["None.", "Owner's Representative (weekly walk).", "Architect (site observation).", "Special inspector.",
            "City building inspector.", "None.", "Owner's Representative; Architect.", "Testing agency technician."]

CP_IDS = {c["id"] for c, _ in CASES}
DR_KEYS = []
for date in DR_DATES:
    assert workday(date), date
    assert SPAN_START <= date <= SPAN_END, date
    o = DR.get(date, {})
    weather = o.get("weather") or weather_default(date)
    acts = active_on(date)[:4]
    if "work" in o:
        work_items = [(a, t) for a, t in o["work"]]
        for a in acts:
            if a not in {x for x, _ in work_items} and len(work_items) < 3 and a != "A1340" and not (date in ("2020-06-03", "2020-06-04", "2020-06-05", "2020-06-08") and ACT[a]["wbs"] in ("Demolition", "Foundations and Structure", "Sitework")):
                work_items.append((a, RNG.choice(PROGRESS)))
    else:
        work_items = [(a, RNG.choice(PROGRESS)) for a in acts]
    if not work_items:
        work_items = []
    firms = {}
    for a, _ in work_items:
        for fm in firm_for(ACT[a]["name"]).split(", "):
            firms.setdefault(fm, RNG.randint(3, 11))
    crew_lines = [f"Example Builders: superintendent, project engineer, {RNG.randint(2, 6)} laborers"]
    crew_lines += [f"{fm}: {n}" for fm, n in sorted(firms.items()) if not fm.startswith("Example Builders")]
    work_txt = "; ".join(f"{ACT[a]['name']} ({a}): {t}" for a, t in work_items) if work_items else \
        "No production work; crews on pumping, erosion control, and housekeeping"
    issues = o.get("issues", "No delays. No safety incidents.")
    visitors = o.get("visitors") or RNG.choice(VISITORS)
    key = f"DR-{date}"
    add_doc("daily_report", key, f"Daily report {date}", date, "gc",
            {"report_date": date, "author": CM_SUPT, "activities": [a for a, _ in work_items]},
            [("Weather", weather, date, "gc"), ("Crew counts", "; ".join(crew_lines) + ".", date, "gc"),
             ("Work performed", work_txt + ".", date, "gc"), ("Issues/delays", issues, date, "gc"),
             ("Visitors", visitors, date, "gc")])
    DR_KEYS.append(key)
    for cp, note in o.get("evidence", []):
        assert cp in CP_IDS, cp
        link(key, cp, "evidence_for", note, "Issues/delays", "Description")

# Field-report / letter evidence from the daily report of the same date
link("DR-2020-02-03", "FR-12", "cites", "The daily report refers to field report FR-12.", "Issues/delays", None)
link("DR-2020-08-10", "FR-33", "cites", "The daily report refers to field report FR-33.", "Issues/delays", None)
link("DR-2020-10-05", "FR-41", "cites", "The daily report refers to field report FR-41.", "Issues/delays", None)

# ---------------------------------------------------------------------------
# 10. Change orders (one per change proposal, demo3 + demo4)
# ---------------------------------------------------------------------------
EQUIP_WORDS = ("lift", "skid steer", "excavator", "forklift", "hoisting", "truck", "pump")


def resolve_cause(c):
    """Return a list of (doc key, to_section) for a case's cause reference."""
    ref = c["cause"]["reference"]
    m = re.match(r"^(RFI-\d+|ASI-\d+)$", ref)
    if m:
        return [(ref, "Answer" if ref.startswith("RFI") else "Description")]
    m = re.match(r"^Submittal (\S+ \S+ \S+)\s*\(", ref)
    if m:
        return [(m.group(1), "Reviewer comments")]
    if c["id"] in CAUSE_SECTION:
        return [CAUSE_SECTION[c["id"]]]
    m = re.match(r"^Architect field order (FO-\d+)$", ref)
    if m:
        return [(m.group(1), "Direction")]
    m = re.match(r"^Field report (FR-\d+)", ref)
    if m:
        return [(m.group(1), "Observation")]
    m = re.match(r"^Notice letter (NL-\d+)$", ref)
    if m:
        return [(m.group(1), "Notice")]
    m = re.match(r"^Erector letter (\S+)$", ref)
    if m:
        return [(f"LTR-ERECTOR-{m.group(1)}", "Letter")]
    m = re.match(r"^Sub letter (\S+)$", ref)
    if m:
        return [(f"LTR-FLATWORK-{m.group(1)}", "Letter")]
    m = re.match(r"^Daily reports (\S+) to (\S+)$", ref)
    if m:
        a, b = m.group(1), m.group(2)
        keys = [k for k in DR_KEYS if a <= k[3:] <= b]
        days, x = [], d(a)
        while x <= d(b):
            if workday(iso(x)):
                days.append(f"DR-{iso(x)}")
            x += dt.timedelta(days=1)
        assert keys == days, (ref, keys, days)
        return [(k, "Issues/delays") for k in keys]
    if ref == "City permit issued late (owner-held permit)":
        return [("PERMIT-2020-01-18", "Schedule effect")]
    return []


RESOLVED = {}
UNRESOLVED = []
for c, src in CASES:
    cs = c["cover_sheet"]
    total = cs["total_requested"]
    parts = []
    for label, k in [("CM direct costs", "cm_direct_costs"), ("subcontractor quotes", "subcontractor_quotes"),
                     ("bond and insurance", "bond_and_insurance"), ("B&O tax", "bo_tax"), ("permit fees", "permit_fees"),
                     ("NSS items", "nss_items"), ("SGC items", "sgc_items"), ("extended SGC for time", "extended_sgc_time")]:
        if cs.get(k):
            parts.append(f"{label} {money(cs[k])}")
    if cs.get("fee"):
        parts.append(f"Fee at {cs['fee_rate'] * 100:g}% {money(cs['fee'])}")
    amount = f"Total requested {money(total)}" + (" (credit)" if total < 0 else "") + (": " + "; ".join(parts) + "." if parts else ".")
    if src == "demo4":
        t = c["time"]
        unit = "calendar days" if t["claimed_calendar"] else "working days"
        time_txt = (f"{t['claimed_days']} {unit} requested. " if t["claimed_days"] else "No time requested. ") + t["narrative"]
    else:
        n = c["time_impact_days"]
        time_txt = f"{n} days requested." if n else "No time requested."
    cause = c["cause"]
    cause_txt = (f"{cause['type']}: {cause['reference']}, event date {cause['event_date']}. "
                 f"Notice given {c['notice_date']}; CP submitted {c['cp_submitted']}.")
    desc = f"{c['title']}. {c['narrative']} Scope basis: {c['scope_context']}"
    meta = {"case_file": f"{src}/data/cases.json", "case_id": c["id"], "cause": cause, "notice_date": c["notice_date"],
            "cp_submitted": c["cp_submitted"], "total_requested": total, "status": "submitted",
            "subcontractors": [q["firm"] for q in c["subcontractor_quotes"]]}
    if "costs_incurred_from" in c:
        meta["costs_incurred_from"] = c["costs_incurred_from"]
    add_doc("change_order", c["id"], f"{c['id']} {c['title']}", c["cp_submitted"], "gc", meta,
            [("Description", desc, c["cp_submitted"], "gc"), ("Cause", cause_txt, cause["event_date"], "gc"),
             ("Amount requested", amount, c["cp_submitted"], "gc"), ("Time requested", time_txt, c["cp_submitted"], "gc")])
    res = resolve_cause(c)
    if not res:
        UNRESOLVED.append((c["id"], cause["reference"]))
    RESOLVED[c["id"]] = res
    for key, sec in res:
        link(c["id"], key, "caused_by", f"{c['id']} cites {cause['reference']} as its cause.", "Cause", sec)
    # Contract clauses the CP is checked against
    cites = ["6.2", "6.3"]
    if c["subcontractor_quotes"]:
        cites.append("6.5.2")
    if cs.get("fee"):
        cites.append("6.5.3")
    descs = " ".join(l.get("desc", "") for l in c["cm_lines"]).lower() + " " + c["narrative"].lower()
    if any(w in descs for w in EQUIP_WORDS):
        cites.append("6.5.4")
    days = c["time"]["claimed_days"] if src == "demo4" else c["time_impact_days"]
    if days:
        cites += ["3.4", "6.5.6"]
    if "T&M" in c["narrative"]:
        cites.append("6.5.7")
    if cause["type"] == "ASI":
        cites.append("6.8")
    if cause["type"] == "RFI response":
        cites.append("7.4")
    if cause["type"] == "Submittal return":
        cites.append("8.3")
    if abs(total) > 250000:
        cites.append("6.7")
    for s in cites:
        link(c["id"], "Contract A", "cites", f"{c['id']} is checked against Section {s}.", "Amount requested" if s.startswith("6.5") else "Cause", s)
    if src == "demo4":
        ids = []
        for r in c["fragnet_truth"]["relationships"]:
            for x in (r["pred"], r["succ"]):
                if x in ACT and x not in ids:
                    ids.append(x)
        for x in ids:
            link(c["id"], "SCH-2020-06-01", "affects", f"{c['id']} fragnet ties to {x}.", "Time requested", x)

CP_SPEC_CITES = [
    ("CP-0201", "Section 22 14 26", "2.02.A"), ("CP-0202", "Section 08 71 00", "2.03.B"),
    ("CP-0223", "Section 08 71 00", "2.03.C"), ("CP-0205", "Section 09 22 16", "2.01.B"),
    ("CP-0212", "Section 02 82 00", "1.03.A"), ("CP-0212", "Section 02 82 00", "3.04.A"),
    ("CP-0235", "Section 02 82 00", "3.06.A"), ("CP-0206", "Section 01 26 00", "1.05.A"),
    ("CP-0221", "Section 01 26 00", "1.05.A"), ("CP-0236", "Section 01 26 00", "1.05.A"),
    ("CP-0230", "Section 01 26 00", "1.04.A"), ("CP-0407", "Section 07 62 00", "3.02.A"),
]
for cp, spec, para in CP_SPEC_CITES:
    link(cp, spec, "cites", f"{cp} scope is measured against {spec} paragraph {para}.", "Description", para)

# ---------------------------------------------------------------------------
# 11. Approved OAC meeting minutes
# ---------------------------------------------------------------------------
MINUTES = [
    (2, "2020-02-13", [
        ("Old business: Building permit was issued 2020-01-18, 12 days after the date in the baseline schedule. CM's notice of 2020-01-14 is on file and CP-0224 has been submitted. Owner's Representative to review.", ["CP-0224", "PERMIT-2020-01-18"]),
        ("Old business: RFI-112 gym roof drains. Architect answered 2020-02-10 and issued ASI-007. CM has sent the response to Cascade Plumbing and will advise on cost in writing.", ["RFI-112", "ASI-007"]),
        ("New business: Field report FR-12, soft organic soils at gym footing F-12. Geotechnical engineer recommends over-excavation and structural fill. CM gave written notice 2020-02-03.", ["FR-12", "CP-0225"]),
        ("New business: Submittal schedule due 2020-03-04 under Section 8.1. CM on track.", []),
        ("RFI log: RFI-104 returned as answered in the Contract Documents.", ["RFI-104"]),
    ]),
    (5, "2020-03-05", [
        ("Old business: RFI-171 classroom fire alarm devices. Architect answered 2020-03-02 (horn/strobes in all classrooms). CM reported that Sentinel Fire Alarm has started layout. Architect noted that statements in these minutes are not notice under Section 7.7.", ["RFI-171", "CP-0222"]),
        ("Old business: ASI-014 corridor doors C101 to C108 to 90-minute assemblies. CM stated it believes ASI-014 adds cost and will give written notice. Architect's position is that the ASI states no change in cost or time.", ["ASI-014", "RFI-109", "CP-0202"]),
        ("Schedule: Abatement - Wing A classrooms on track for completion 2020-03-19.", []),
        ("New business: RFI-124 coping gauge at the gym parapet is with the Architect.", ["RFI-124"]),
    ]),
    (13, "2020-04-30", [
        ("Old business: ASI-040 seismic bracing. CP-0226 totals $310,117.50, above the Owner's Representative's $250,000 approval limit; Owner to place it on the Board agenda under Section 6.7.", ["ASI-040", "CP-0226"]),
        ("Old business: RFI-180 kitchen hood relocated to the south wall (answered 2020-04-20). CM pricing.", ["RFI-180", "CP-0228"]),
        ("Submittals: 09 22 16-01 framing returned Revise and Resubmit on 2020-04-20; resubmittal expected next week.", ["09 22 16-01"]),
        ("Schedule: Abatement - existing gym and commons complete 2020-04-29; clearance air testing starts 2020-04-30.", []),
    ]),
    (19, "2020-06-11", [
        ("Old business: Rain 2020-06-03 to 2020-06-08 flooded the addition footprint. CM pumped the site and gave written notice 2020-06-10. Excavation and shoring - addition started 2020-06-09.", ["CP-0411", "DR-2020-06-03"]),
        ("New business: Owner email of 2020-06-08 directed a stage lift pit in the addition and acoustic panels in the gym. CM will price both.", ["OE-2020-06-08", "CP-0401", "CP-0230"]),
        ("New business: Puget Steel Erectors letter of 2020-06-10 on crane availability. Owner's Representative noted the erector is CM's subcontractor.", ["LTR-ERECTOR-2020-06-10", "CP-0409"]),
        ("RFI log: RFI-214 gym truss bearings is open; Architect to respond by 2020-06-12.", ["RFI-214"]),
        ("Old business: RFI-131 corridor access panels proceeding on T&M; tags signed daily by the CM superintendent and the Owner's Representative.", ["RFI-131", "CP-0206"]),
        ("Schedule: Update with data date 2020-06-01 distributed.", ["SCH-2020-06-01"]),
    ]),
    (22, "2020-07-02", [
        ("Old business: Storm of 2020-06-26 flooded the open underslab utility trench at the addition. Dewatering and re-excavation under way.", ["CP-0412", "DR-2020-06-26"]),
        ("New business: Owner email of 2020-06-29 changes addition classroom flooring to rubber tile and moves the locker room benches. Northwest Floors has also reported a crew shortage for the same period.", ["OE-2020-06-29", "CP-0413", "CP-0232"]),
        ("RFI log: RFI-233 storefront head subframing answered 2020-06-24; RFI-183 science room gas shutoffs answered 2020-06-22.", ["RFI-233", "CP-0407", "RFI-183"]),
        ("ASIs issued since last meeting: ASI-061 (Wing A casework), ASI-070 (sprinkler mains), ASI-075 (sunshades). CM reviewing for cost and time.", ["ASI-061", "ASI-070", "ASI-075"]),
        ("Old business: Cornerstone Flatwork crew shortage letter of 2020-06-15. Owner's Representative noted this is a subcontractor matter.", ["LTR-FLATWORK-2020-06-15", "CP-0410"]),
    ]),
    (28, "2020-08-13", [
        ("Old business: Field report FR-33, asbestos mastic under flooring in classrooms 110 to 116, found 2020-08-10. Clearwater Abatement mobilized 2020-08-11. CM gave notice 2020-08-10.", ["FR-33", "CP-0212"]),
        ("Old business: Courtyard hose bibbs done on T&M. Architect reminded CM that Section 6.5.7 requires tags signed by the CM superintendent and the Owner's Representative.", ["CP-0236"]),
        ("CP log: CP-0235 (patch and paint per ASI-050) and CP-0211 (staff lot lighting) under review.", ["CP-0235", "ASI-050", "CP-0211"]),
        ("RFI log: RFI-189 elevator pit sump answered 2020-07-27.", ["RFI-189"]),
    ]),
    (36, "2020-10-08", [
        ("Old business: Field report FR-41, abandoned vault on the storm line to the playfield. Storm line rerouted 2020-10-06 per the civil engineer.", ["FR-41", "CP-0217"]),
        ("RFI log: RFI-166 rooftop unit curbs is open; Architect expects to answer 2020-10-12. RFI-158 bleacher anchors answered 2020-09-21.", ["RFI-166", "RFI-158", "CP-0216"]),
        ("RFI log: RFI-152 stair nosings answered 2020-09-14; CP-0215 under review.", ["RFI-152", "CP-0215"]),
    ]),
]
for n, mdate, items in MINUTES:
    approved_on = add_days(mdate, 7)
    key = f"OAC-{n:02d}"
    header = (f"OAC Meeting No. {n}, {mdate}, site office. Attendees: {OWNER_REP}; {ARCH}; {CM_PM}; {CM_SUPT}. "
              f"These minutes were approved as written at OAC Meeting No. {n + 1} on {approved_on}. "
              "Minutes are for record only and are not notice under Section 7.7.")
    pieces = [("Header", header, mdate, "gc")]
    for i, (text, refs) in enumerate(items, 1):
        pieces.append((f"Item {n}.{i}", text, mdate, "gc"))
    add_doc("minutes", key, f"OAC Meeting No. {n} minutes ({mdate}), approved", mdate, "gc",
            {"meeting_no": n, "meeting_date": mdate, "status": "approved", "approved_on": approved_on,
             "approved_at": f"OAC Meeting No. {n + 1}"}, pieces)
    for i, (text, refs) in enumerate(items, 1):
        for r in refs:
            link(key, r, "discussed", f"OAC {n} item {n}.{i} discusses {r}.", f"Item {n}.{i}", None)

# ---------------------------------------------------------------------------
# 12. Self-check
# ---------------------------------------------------------------------------
ACT_MENTIONS = []


def self_check():
    errors = []
    out = []
    sections = {k: {p["section"] for p in doc["pieces"]} for k, doc in DOC_BY_KEY.items()}
    # every case cause resolves to an existing document
    for c, _ in CASES:
        res = RESOLVED.get(c["id"], [])
        if not res:
            errors.append(f"{c['id']}: cause '{c['cause']['reference']}' not resolved")
        for key, sec in res:
            if key not in DOC_BY_KEY:
                errors.append(f"{c['id']}: cause doc {key} missing")
    # links: endpoints and pinned sections exist
    for l in LINKS:
        for end, sec in (("from", "from_section"), ("to", "to_section")):
            if l[end] not in DOC_BY_KEY:
                errors.append(f"link endpoint missing: {l}")
            elif l[sec] is not None and l[sec] not in sections[l[end]]:
                errors.append(f"link {end} section '{l[sec]}' not in {l[end]}")
        if not l["note"]:
            errors.append(f"link without note: {l}")
    # date consistency: RFI answer on or before the CP event date; answer equals event date
    for c, _ in CASES:
        if c["cause"]["type"] == "RFI response":
            rfi = DOC_BY_KEY[c["cause"]["reference"]]
            ans = [p for p in rfi["pieces"] if p["section"] == "Answer"][0]["piece_date"]
            if not ans <= c["cause"]["event_date"]:
                errors.append(f"{c['id']}: RFI answer {ans} after event {c['cause']['event_date']}")
            if ans != c["cause"]["event_date"]:
                errors.append(f"{c['id']}: RFI answer {ans} differs from event {c['cause']['event_date']}")
        if c["cause"]["type"] == "ASI" and DOC_BY_KEY[c["cause"]["reference"]]["issued_on"] != c["cause"]["event_date"]:
            errors.append(f"{c['id']}: ASI date mismatch")
        if c["cause"]["type"] == "Submittal return":
            sub = DOC_BY_KEY[RESOLVED[c["id"]][0][0]]
            if sub["meta"]["returned_on"] != c["cause"]["event_date"]:
                errors.append(f"{c['id']}: submittal return date mismatch")
        for key, _ in RESOLVED[c["id"]]:
            doc = DOC_BY_KEY[key]
            if doc["kind"] in ("other", "daily_report") and doc["issued_on"] > c["cp_submitted"]:
                errors.append(f"{c['id']}: cause doc {key} dated after CP submission")
    # daily reports inside the schedule span, on working days; named activities exist with the right name
    for doc in DOCS:
        if doc["kind"] == "daily_report":
            if not (SPAN_START <= doc["issued_on"] <= SPAN_END):
                errors.append(f"{doc['key']} outside schedule span")
            if not workday(doc["issued_on"]):
                errors.append(f"{doc['key']} not a working day")
            for p in doc["pieces"]:
                named = re.findall(r"([A-Z][^;:()]*?) \((A\d{4})\)", p["body"])
                ACT_MENTIONS.append(len(named))
                for name, aid in re.findall(r"([A-Z][^;:()]*?) \((A\d{4})\)", p["body"]):
                    if aid not in ACT or ACT[aid]["name"] != name.strip():
                        errors.append(f"{doc['key']}: activity '{name}' ({aid}) not in schedule")
    # minutes: approved; RFI/ASI they discuss already issued; CP causes already happened
    for doc in DOCS:
        if doc["kind"] == "minutes":
            if doc["meta"]["status"] != "approved" or "approved" not in doc["pieces"][0]["body"]:
                errors.append(f"{doc['key']} not approved")
    for l in LINKS:
        if l["relation"] == "discussed":
            m = DOC_BY_KEY[l["from"]]["issued_on"]
            t = DOC_BY_KEY[l["to"]]
            if t["kind"] == "change_order":
                if t["meta"]["cause"]["event_date"] > m:
                    errors.append(f"{l['from']} discusses {l['to']} before its event")
            elif t["kind"] in ("rfi", "asi", "submittal", "other", "daily_report") and t["issued_on"] > m:
                errors.append(f"{l['from']} discusses {l['to']} before it was issued")
    # piece bodies non-empty; contract pieces are verbatim (after emphasis removal)
    plain = unemph(CONTRACT_MD)
    for doc in DOCS:
        if not doc["pieces"]:
            errors.append(f"{doc['key']} has no pieces")
        for p in doc["pieces"]:
            if not p["body"].strip():
                errors.append(f"{doc['key']} piece {p['section']} empty")
            if p["party"] not in ("sub", "gc", "architect", "owner"):
                errors.append(f"{doc['key']} bad party")
        if doc["kind"] == "contract":
            for p in doc["pieces"]:
                if p["body"] not in plain:
                    errors.append(f"contract piece {p['section']} not verbatim")
        if doc["source"] != "synthetic":
            errors.append(f"{doc['key']} not synthetic")
    for need in ("12.1", "6.2", "6.5.2", "6.5.3", "6.5.6", "7.4", "Exhibit E 01 26 00"):
        if need not in CONTRACT_SECTIONS:
            errors.append(f"contract section {need} missing")
    out.append(f"cases checked: {len(CASES)}; causes resolved: {sum(1 for v in RESOLVED.values() if v)}; unresolved: {len(UNRESOLVED)}")
    out.append(f"schedule activity mentions in daily reports checked against schedule.json: {sum(ACT_MENTIONS)}")
    out.append(f"links checked: {len(LINKS)}; documents: {len(DOCS)}; pieces: {sum(len(x['pieces']) for x in DOCS)}")
    return errors, out


# ---------------------------------------------------------------------------
# 13. Write outputs
# ---------------------------------------------------------------------------
def render_md(doc):
    lines = [SYN_NOTE, "", f"# {doc['title']}", "",
             f"- Number: {doc['number']}", f"- Kind: {doc['kind']}", f"- Issued: {doc['issued_on']}",
             f"- Author party: {doc['author_party']}", f"- Source: {doc['source']} ({doc['external_id']})"]
    for k, v in doc["meta"].items():
        lines.append(f"- {k}: {json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v}")
    lines.append("")
    for p in doc["pieces"]:
        lines.append(f"## {p['section']}")
        lines.append(f"*{p['piece_date']}, {p['party']}*")
        lines.append("")
        lines.append(p["body"])
        lines.append("")
    outs = [l for l in LINKS if l["from"] == doc["key"]]
    ins = [l for l in LINKS if l["to"] == doc["key"]]
    if outs or ins:
        lines.append("## Links")
        for l in outs:
            lines.append(f"- {l['relation']} -> {l['to']}" + (f" ({l['to_section']})" if l["to_section"] else "") + f": {l['note']}")
        for l in ins:
            lines.append(f"- {l['from']}" + (f" ({l['from_section']})" if l["from_section"] else "") + f" {l['relation']} this: {l['note']}")
        lines.append("")
    return "\n".join(lines)


def main():
    errors, out = self_check()
    docs_dir = os.path.join(OUT, "docs")
    if os.path.isdir(docs_dir):
        shutil.rmtree(docs_dir)
    total = 0
    out_docs = [x for x in DOCS if x["key"] not in REPLACED]
    for doc in out_docs:
        path = os.path.join(ROOT, doc["file"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = render_md(doc).encode("utf-8")
        with open(path, "wb") as f:
            f.write(data)
        total += len(data)
    bundle = {"project": PROJECT, "documents": out_docs, "links": LINKS}
    data = (json.dumps(bundle, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    with open(os.path.join(OUT, "bundle.json"), "wb") as f:
        f.write(data)
    # summary
    by_kind = {}
    for doc in DOCS:
        by_kind[doc["kind"]] = by_kind.get(doc["kind"], 0) + 1
    by_rel = {}
    for l in LINKS:
        by_rel[l["relation"]] = by_rel.get(l["relation"], 0) + 1
    print("documents by kind:", json.dumps(dict(sorted(by_kind.items()))))
    print("links by relation:", json.dumps(dict(sorted(by_rel.items()))))
    for line in out:
        print(line)
    if REPLACED:
        print("replaced by real documents (not written):", sorted(REPLACED))
    print(f"bundle.json: {len(data):,} bytes; docs/*.md: {len(out_docs)} files, {total:,} bytes; total {len(data) + total:,} bytes")
    if UNRESOLVED:
        print("UNRESOLVED causes:", UNRESOLVED)
    if errors:
        print(f"SELF-CHECK FAILED ({len(errors)}):")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("SELF-CHECK OK")


if __name__ == "__main__":
    main()
