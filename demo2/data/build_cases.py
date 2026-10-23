#!/usr/bin/env python3
"""Generate Demo 2's synthetic test set: 30 documents a GC receives, each labeled.

Each case is a short message the CM receives (RFI response, ASI, submittal return, owner email,
meeting minutes, field report, third-party letter), written against the Demo 1 synthetic contract.
The label says whether it is a CLARIFICATION (no change to cost or time) or a POSSIBLE CHANGE that
needs written notice, which Section 6.2 rule sets the clock, and why. The notice due date is not
typed by hand: it is computed from the event date and the rule by deadlines.py (Section 1.4 rolls a
deadline that lands on a weekend or holiday to the next business day).

Outputs:
  data/cases.json        what the classifier sees (no labels)
  data/answer_key.json   the labels, used only by evaluate.py

Run:  python data/build_cases.py
"""
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from deadlines import notice_due, is_business_day  # noqa: E402

C, P = "CLARIFICATION", "POSSIBLE CHANGE"

# id, source, event_date, from, text, label, notice_rule, sections, tricky, why
CASES = [
    # ---------------- clarifications: no change to cost or time ----------------
    ("C01", "RFI response", "2020-02-04", "Architect",
     "RFI 031 response: Install the stair guardrail at 42 inches as dimensioned on A-301. The 36-inch note on A-302 is a drafting error. Guardrail type and materials are unchanged.",
     C, "none", ["7.4"], False, "Resolves a conflict between two sheets without adding work; an RFI response alone does not change cost or time."),
    ("C02", "RFI response", "2020-02-11", "Architect",
     "RFI 038 response: Corridor wall paint color is SW 7006 Extra White, as listed in the finish schedule on A-601.",
     C, "none", ["7.4"], False, "Points to information already in the documents."),
    ("C03", "RFI response", "2020-03-03", "Architect",
     "RFI 052 response: Yes, the existing brick at the north entry remains, as shown on demolition plan D-101. Clean and repoint per Section 04 01 20.",
     C, "none", ["7.4"], False, "Confirms base scope shown on the drawings and specs."),
    ("C04", "RFI response", "2020-03-10", "Architect",
     "RFI 057 response: Provide the floor drain shown on P-201 at Room 114. It also appears on the plumbing fixture schedule. No additional drains are required.",
     C, "none", ["7.4"], False, "Work is already shown in two places in the documents."),
    ("C05", "ASI", "2020-03-24", "Architect",
     "ASI-07: Hardware set HW-3 in the door hardware schedule lists a knob trim by mistake. Use the lever trim already specified in Section 08 71 00. No change in cost or time.",
     C, "none", ["6.8"], True, "A true no-cost ASI: it corrects a typo to match the spec, so nothing is added."),
    ("C06", "Submittal return", "2020-04-07", "Architect",
     "Submittal 05 50 00-003, Approved as Noted: Provide the manufacturer's standard finish as specified. Confirm anchor spacing matches structural detail 4/S-401 before fabrication.",
     C, "none", ["8.3"], False, "The note asks the CM to comply with the spec and drawings; no added work."),
    ("C07", "RFI response", "2020-04-14", "Architect",
     "RFI 071 response: Classroom whiteboards mount at 30 inches above finished floor to the bottom edge, per detail 5/A-702.",
     C, "none", ["7.4"], False, "Dimension is already in a detail."),
    ("C08", "Owner email", "2020-04-21", "Owner's Representative",
     "Please send the updated three-week look-ahead schedule before Friday's coordination meeting. Thanks.",
     C, "none", [], False, "An administrative request; no direction to change the Work."),
    ("C09", "RFI response", "2020-05-05", "Structural Engineer via Architect",
     "RFI 080 response: The steel connection at grid C/4 is bolted as shown in detail 7/S-501. The welded-connection general note applies only to the gymnasium roof framing.",
     C, "none", ["7.4"], False, "Explains which existing note applies; no new work."),
    ("C10", "RFI response", "2020-06-02", "Architect",
     "RFI 094 response: Curtain wall sealant joints are 1/2 inch, as shown on the approved shop drawings for Submittal 08 44 13-002.",
     C, "none", ["7.4"], False, "Refers to an already approved submittal."),
    ("C11", "Meeting minutes", "2020-06-09", "CM (minutes of Coordination Meeting #22)",
     "Coordination Meeting #22: Architect confirmed fire alarm devices are located per the approved fire alarm drawings. No changes were discussed. Next meeting June 16.",
     C, "none", ["7.7"], False, "Minutes record a confirmation; no direction or change."),
    ("C12", "RFI response", "2020-06-23", "Architect",
     "RFI 101 response: The existing library ceiling grid is removed and replaced as shown on demolition plan D-201 and reflected ceiling plan A-401. This is base scope.",
     C, "none", ["7.4"], False, "Work is shown in the base documents."),
    ("C13", "Owner email", "2020-07-14", "Owner's Representative",
     "We'd like to see options for upgrading the gym floor finish to a sport urethane. Please don't proceed with anything yet. Just send rough pricing ideas when you have a chance.",
     C, "none", [], True, "Sounds like a change, but it is a request for ideas with an explicit instruction not to proceed, so there is no direction yet."),
    ("C14", "Submittal return", "2020-08-04", "Mechanical Engineer via Architect",
     "Submittal 22 11 23-001, Revise and Resubmit: The submitted pump delivers 95 gpm; Section 22 11 23 requires 120 gpm. Resubmit a pump that meets the specification.",
     C, "none", ["8.3"], True, "A rejection that enforces the existing spec is not a change; the CM must meet what was specified."),
    ("C15", "RFI response", "2020-08-18", "Architect",
     "RFI 118 response: Roof drain locations are as shown on plumbing plan P-301. Architectural roof plan A-111 shows the same locations. No additional drains.",
     C, "none", ["7.4"], False, "Confirms consistent information already in the documents."),

    # ---------------- possible changes: notice required ----------------
    ("P01", "RFI response", "2020-02-18", "Architect",
     "RFI 041 response: Add a second layer of 5/8-inch Type X gypsum board to the Level 2 corridor walls to achieve a 2-hour rating. The drawings show a single layer.",
     P, "6.2(a)", ["7.4", "6.2(a)"], False, "Adds material and labor beyond the drawings; an RFI response that changes cost needs notice within 7 days."),
    ("P02", "ASI", "2020-03-17", "Architect",
     "ASI-11: Relocate the science classroom fume hood from the north wall to the east wall, including a new exhaust duct route to the roof. No change in cost or time.",
     P, "6.2(a)", ["6.8", "6.2(a)"], True, "Labeled no-cost, but moving the hood and rerouting the duct adds work; Section 6.8 sends this to 6.2(a)."),
    ("P03", "Submittal return", "2020-03-31", "Architect",
     "Submittal 09 65 19-001, Approved as Noted: Substitute sheet linoleum for the specified vinyl composition tile in Rooms 201 through 210 to meet the district's new flooring standard.",
     P, "6.2(a)", ["8.3", "6.2(a)"], True, "An 'approved as noted' comment that swaps the product changes cost; Section 8.3 sends this to 6.2(a)."),
    ("P04", "Daily log (oral direction)", "2020-04-16", "Owner's Representative (recorded by CM superintendent)",
     "Site walk, 9:30 am: Owner's Representative directed the CM to add two exterior security cameras at the bus loop before school opens. The cameras are not shown on the drawings.",
     P, "6.2(b)", ["6.2(b)"], True, "An oral direction to add work not shown; 7 days from the direction."),
    ("P05", "Owner email", "2020-04-28", "Owner's Representative",
     "Per the district's new security policy, provide card readers on all classroom doors instead of the keyed locks in the hardware schedule. Please proceed.",
     P, "6.2(b)", ["6.2(b)"], False, "A written direction that replaces specified hardware with costlier work."),
    ("P06", "Field report", "2020-02-15", "CM excavation foreman",
     "Saturday shift: While excavating for the new elevator pit, the crew found an abandoned fuel oil tank about 6 feet below grade. It is not shown on the survey or the geotechnical report. Work in that area stopped.",
     P, "6.2(c)", ["6.2(c)"], True, "A concealed condition that differs from the documents. Observed on a Saturday, so day 7 is also a Saturday and the deadline rolls to Monday (Section 1.4)."),
    ("P07", "Field report", "2020-05-12", "CM demolition foreman",
     "Opening the original 1908 east wall, the crew found the steel window lintels heavily corroded. The drawings assume the existing lintels remain in place.",
     P, "6.2(c)", ["6.2(c)"], False, "A concealed condition that differs from what the drawings assume."),
    ("P08", "Meeting minutes", "2020-06-16", "CM (minutes of Coordination Meeting #23)",
     "Coordination Meeting #23: Owner's Representative stated the district wants the library mezzanine railing raised from 42 to 48 inches and asked the CM to proceed.",
     P, "6.2(b)", ["7.7", "6.2(b)"], True, "The minutes are not notice (7.7), but they record an oral direction to change the work, so 6.2(b) notice is due 7 days after the meeting."),
    ("P09", "Building department notice", "2020-07-07", "City building department",
     "Notice to permit holders: A Seattle Energy Code amendment now in effect requires R-38 roof insulation on projects whose roof inspection has not yet occurred. Your project's roof inspection is pending.",
     P, "6.2(d)", ["6.2(d)"], True, "A third-party event, not an Owner or Architect document, that may increase cost; 14 days after CM learns of it."),
    ("P10", "Utility letter", "2020-07-21", "Seattle City Light",
     "City Light will not energize the new electrical service until a transformer vault is built at the service entrance. The vault is not in your contract documents.",
     P, "6.2(d)", ["6.2(d)"], False, "A utility requirement outside the documents; 14 days."),
    ("P11", "RFI response", "2020-05-18", "Architect",
     "RFI 087 response: Provide fire-rated access panels at all 14 ceiling access locations above the Level 1 corridor. The drawings call for standard panels.",
     P, "6.2(a)", ["7.4", "6.2(a)"], True, "Upgrades a product; 7 days lands on Memorial Day (May 25, 2020), so notice is due the next business day (Section 1.4)."),
    ("P12", "ASI", "2020-08-11", "Architect",
     "ASI-15: Add wood blocking for owner-furnished TV mounts in 22 classrooms. CM to submit any cost and time impact.",
     P, "6.2(a)", ["6.8", "6.2(a)"], False, "An ASI that openly adds work."),
    ("P13", "Submittal return", "2020-08-25", "Electrical Engineer via Architect",
     "Submittal 26 51 00-002, Revise and Resubmit: Provide seismic bracing for all suspended light fixtures per the district's updated standard. Section 26 51 00 does not require this bracing.",
     P, "6.2(a)", ["8.3", "6.2(a)"], True, "Unlike a rejection that enforces the spec, this comment requires work beyond the spec."),
    ("P14", "Owner email", "2020-09-15", "Owner's Representative",
     "The district needs the gym finished two weeks early to host the regional tournament. Please accelerate and work overtime as needed.",
     P, "6.2(b)", ["6.2(b)"], False, "A written direction to accelerate affects cost and time."),
    ("P15", "RFI response", "2020-09-29", "Architect",
     "RFI 132 response: Extend the new storm drain line 40 feet to connect at the existing manhole on the east side of the site. The civil drawings end the line at the property line.",
     P, "6.2(a)", ["7.4", "6.2(a)"], False, "Adds 40 feet of pipe beyond the drawings."),
]


def build():
    cases, key = [], []
    rolls = []
    for (cid, source, event_date, sender, text, label, rule, sections, tricky, why) in CASES:
        due = notice_due(event_date, rule)
        if label == C:
            assert rule == "none" and due is None, cid
        else:
            assert rule != "none" and due is not None, cid
            plain = date.fromisoformat(event_date).toordinal() + (14 if rule == "6.2(d)" else 7)
            if date.fromisoformat(due).toordinal() != plain:
                rolls.append(cid)
        cases.append({"id": cid, "source": source, "event_date": event_date, "from": sender, "text": text})
        key.append({"id": cid, "label": label, "notice_rule": rule, "sections": sections,
                    "notice_due": due, "tricky": tricky, "why": why})
    # The only deadlines that roll forward should be the two designed to (weekend and holiday).
    assert sorted(rolls) == ["P06", "P11"], rolls
    assert all(is_business_day(date.fromisoformat(k["notice_due"])) for k in key if k["notice_due"])
    assert len({c["id"] for c in cases}) == 30
    return cases, key


def main():
    cases, key = build()
    here = Path(__file__).resolve().parent
    (here / "cases.json").write_text(json.dumps({"cases": cases}, indent=2) + "\n", encoding="utf-8")
    meta = {
        "description": "Labels for Demo 2's 30 synthetic documents. Used only by evaluate.py; never shown to the model.",
        "status": "Written by the same author as the contract; not yet independently reviewed by a teammate.",
        "label_counts": dict(Counter(k["label"] for k in key)),
        "notice_rule_counts": dict(Counter(k["notice_rule"] for k in key)),
        "tricky_cases": sum(k["tricky"] for k in key),
        "deadline_rolls": ["P06 (Saturday)", "P11 (Memorial Day)"],
    }
    (here / "answer_key.json").write_text(json.dumps({"meta": meta, "cases": key}, indent=2) + "\n", encoding="utf-8")
    print(f"OK: {len(cases)} cases. {meta['label_counts']}. Rules: {meta['notice_rule_counts']}. Tricky: {meta['tricky_cases']}.")


if __name__ == "__main__":
    main()
