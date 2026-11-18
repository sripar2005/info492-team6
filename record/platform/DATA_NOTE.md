# Platform sample data: data note

## What is synthetic
Everything in `record/platform/` is synthetic test data, written with AI assistance (an AI assistant working as an independent data writer) for INFO 492 C coursework. No real firm, person or project is represented. Company names come from the existing synthetic cases and bundle; the Owner, Architect and GC/CM names are the placeholders already used in contract A and the bundle (none were invented). Field-sample first names are invented.

The writer read only the data files listed in `SPEC.md` (the bundle, contract A, the demo3 and demo4 cases, the June 2020 schedule and its data note). It did not open any code in `assets/`, `record/*.py`, `demo3/*.py`, `demo4/*.py` or `tools/`.

## How it was built
Run `python3 record/platform/build/build.py` from the repo root (standard library only). It rewrites every file here and stops on any failed check:
- `platform.json`: 32 companies, 27 contracts (prime, design, 25 subcontracts), 47 SOV lines, 3 schedule versions, 52 sub requests on 48 changes, 9 field samples.
- `docs/`: one subcontract per first-tier sub (three different forms: "§" agreement, "Section" short form, "¶" trade form) and `design_summary.md`.
- `schedule_baseline.json`, `schedule_u2.json`: same format as `demo4/data/schedule.json`.
- `answer_key.json`: flow-down gaps, cost per day, rollups, visibility, plus extra checks.

Checks the script asserts: every term sentence is verbatim in its contract file (prime terms in both `demo1/data/synthetic_contract.md` and the bundle's contract pieces) and contains its value (numbers as written, with or without thousands commas; text values as substrings; booleans by a marker phrase such as "is a condition precedent" vs "is not a condition precedent", with the opposite marker absent); sub request amounts match the cases' `subcontractor_quotes` per change except the deliberate mismatches; request lines add to the request amount (except the one transposed total); at least two flow-down gaps and at least one clean subcontract; the SOV ties to contract A Exhibits A and C ($26,240,507); schedule files load as JSON with the same keys as the June update; every relationship references an existing activity id.

The schedules come from an independent forward-pass CPM in `build.py` using the conventions in `demo4/data/DATA_NOTE.md`. It reproduces all 91 forecast dates printed in the bundle's June 2020 schedule document and the as-planned finish of 2021-06-30.

## Companies and subcontracts
First-tier subs are every firm in the cases' `subcontractor_quotes`, plus Cornerstone Flatwork (named in the bundle's 2020-06-15 letter, the unnamed flatwork sub on CP-0410). Lower-tier firms (tier 2) are Lakeside Low Voltage and Ridgeline Carpentry (under Sound Electric; Ridgeline is also under Harmony Acoustics, listed in `also_under`), Northwest Controls (under Rainier Mechanical) and Ironwood Structural (under Sound Electric, named only in the CP-0234 email quote). Lower-tier firms have no subcontract with the GC/CM.

| Sub | Notice window | Prime notice flows down | GC days left (7 - window) | Result | Pricing days |
|---|---|---|---|---|---|
| Cascade Plumbing | 3 calendar days | yes | 4 | clean | 7 |
| Northwest Door & Hardware | 3 calendar days | yes | 4 | clean | 7 |
| Sound Electric | 3 calendar days | yes | 4 | clean | 7 |
| Puget Steel Erectors | 10 business days | no | -5 | **gap** | 10 |
| Evergreen Framing | 3 calendar days | yes | 4 | clean | 7 |
| Sentinel Fire Protection | 4 calendar days | yes | 3 | clean | 7 |
| Clearwater Abatement | 3 calendar days | yes | 4 | clean | 7 |
| Summit Athletic Interiors | 5 calendar days | yes | 2 | clean | 10 |
| Timberline Casework | 4 calendar days | yes | 3 | clean | 10 |
| Evergreen Flooring | 5 calendar days | yes | 2 | clean | 7 |
| Rainier Mechanical | 2 calendar days | yes | 5 | clean | 21 |
| Clearview Glazing | 5 calendar days | yes | 2 | clean | 7 |
| Sentinel Fire Alarm | 4 calendar days | yes | 3 | clean | 7 |
| Granite Earthworks | 14 calendar days | no | -7 | **gap** | 10 |
| Pacific Specialties | 5 calendar days | yes | 2 | clean | 7 |
| Harmony Acoustics | 21 calendar days | no | -14 | **gap** | 14 |
| Brightline Painting | 5 calendar days | yes | 2 | clean | 7 |
| Granite Concrete | 3 calendar days | yes | 4 | clean | 7 |
| Evergreen Site Works | 4 calendar days | yes | 3 | clean | 10 |
| Summit Roofing | 10 calendar days | no | -3 | **gap** | 10 |
| Cascade Glazing | 4 calendar days | yes | 3 | clean | 10 |
| Northwest Floors | 4 calendar days | yes | 3 | clean | 10 |
| Olympic Structural | 5 calendar days | yes | 2 | clean | 7 |
| Cascade Coatings | 5 calendar days | yes | 2 | clean | 7 |
| Cornerstone Flatwork | 5 calendar days | yes | 2 | clean | 7 |

## Deliberate quirks
- **Flow-down gaps.** Granite Earthworks (14 days), Harmony Acoustics (21 days), Puget Steel Erectors (10 *business* days: at least 12 calendar days if the event falls on a weekend, 14 if on a weekday; the key uses the shortest, 12) and Summit Roofing (10 days). Summit Roofing's § 2.1 is a general flow-down that names notice procedures, but § 4.2 says "Notwithstanding § 2.1, the notice period in this § 4.2 governs", so its `notice_flowdown` is false and the 10-day window governs. All other subs are clean with 2 to 5 calendar days; no sub sits at a 0 or 1 day margin, so the result does not depend on how one counts the GC's turnaround.
- **Pricing windows.** Rainier Mechanical has 21 days to price a change, which uses the GC/CM's whole 21-day CP window (§ 6.3) and is 7 days over a 14-day Proposal Request window. Harmony Acoustics has 14 days (0 days left after a Proposal Request).
- **Markups above the prime contract.** Pacific Specialties' subcontract allows 12% on its own work and Sound Electric's allows 10% on lower-tier work; contract A § 6.5.2 allows 10% and 5%. These match the quotes in CP-0229 and CP-0210. Cascade Plumbing's subcontract says 10%, so its 15% quotes (CP-0209, CP-0231) break both contracts.
- **Cost per day.** Time-based SGC lines in the SOV total $1,550,000, or $2,870.37 per day over 540 days. Contract A § 5.2 states $3,185 per day, which is all SGC ($1,720,000) / 540 and so includes fixed lines (trailer mobilization, reproduction, signage). The two disagree by $314.63 per day. NSS lines are not counted as general conditions, because contract A ties the daily rate to SGC only.
- **Sub request mismatches** (marked `deliberate_mismatch` in the answer key):
- **CP-0212**: requests $19,410.00 vs case quotes $19,140.00. Transposed total: the request's lines add to $19,140.00 (the case's quote) but the request total reads $19,410.00.
- **CP-0406**: requests $57,849.00 vs case quotes $55,099.00. Sub's request includes a $2,500 crane pick (plus 10% markup, $2,750 in all) that the GC/CM struck before the CP, because hoisting and crane are already in NSS (contract A Exhibit C). The case's quote is the negotiated amount.
- **Split request.** Harmony Acoustics sent CP-0403 in two requests: its own work first, then a supplement (`-S1`) with Ridgeline Carpentry's lower-tier price and markup. Together they match the case quote, so the rollup must sum both.
- **Firm in two tiers.** Sentinel Fire Protection is a first-tier sub and also a lower tier under Rainier Mechanical on CP-0504. It is listed once, as tier 1.
- **Design agreement review times.** `design_summary.md` gives the Architect 21 days for submittals and 14 for resubmittals; contract A § 8.2 promises the GC/CM 14 and 10. RFI times match.
- **Update 2.** Data date 2020-09-01, caused by CP-0401, CP-0402 (Owner and Architect changes, both compensable in the demo4 answer key). Their fragnet activities are added with the cases' own ids and logic. Progress through the data date follows the forecast exactly (no new slips): 34 activities complete, 3 in progress. Forecast Substantial Completion moves from 2021-07-02 to 2021-07-19 (17 calendar days; alone, CP-0401 gives 11 and CP-0402 gives 7).
- **Baseline.** Same activities, durations and logic as the June update, no actuals, data date 2020-02-03. The June update's slips are in its actual dates, not its durations, so the baseline finish is 2021-06-30.

## Limits
- One writer produced the contracts, requests and answer key, so the key checks consistency with this writer's reading, not an independent legal review.
- Sub request narratives are short and cleaner than real ones. Submitted dates are placed between each change's event and CP dates by a fixed rule.
- Update 2 has no out-of-sequence progress or new slips.
