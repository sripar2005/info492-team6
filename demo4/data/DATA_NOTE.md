# Demo 4 data note

## What is synthetic
Everything in this folder is synthetic test data written for INFO 492 C coursework. No real project, schedule, contract, firm, or person is represented.
- **Schedule.** A made-up school modernization and addition on contract A (`demo1/data/synthetic_contract.md`): Notice to Proceed 2020-02-03, contract Substantial Completion 2021-07-27 (540 calendar days), data date 2020-06-01.
- **Contract B** (`contract_b.md`, `contract_b.pdf`). A second invented GC/CM contract with different numbers from contract A (markup 8% / 4% / 12%, Fee 4.5% on CM direct costs and subcontractor quotes, 30% labor burden, owned equipment at 70% of Blue Book, $150,000 approval limit, 10-day notice except 21 days for other events, 420-day contract time, $1,800/day liquidated damages, $2,450/day extended general conditions, only Owner-caused critical-path delay compensable, concurrent delay gets time but no money). Each key term is stated once in prose. Unrelated numbers (insurance limits, retainage, payment days, warranty years, a fixed base Fee, CM Contingency) are there as distractors.
- **Change proposals.** 15 CPs (CP-0401 to CP-0415) on contract A, each with a time section, a plain-English time narrative, and the true fragnet.

## How it was built
Run `python3 demo4/build_data.py` from the repo root. It rebuilds every file here and stops on any failed check.
1. `schedule_src.py` lists 91 activities in 11 WBS groups and their logic. `cpm_ref.py` (an independent Python CPM, standard library only; `python3 demo4/cpm_ref.py` runs its self-tests) schedules it as planned. The script then applies a few slips (A1220 +2, A1300 +1, A1440 +3 working days) and records progress at the data date: 18 activities complete and 3 in progress.
2. The updated schedule has 142 relationships (3 FF, 113 FS, 1 SF, 25 SS; 28 with lags), one SNET constraint (Owner furniture, A1890), and Washington State legal holidays for 2020 and 2021. Forecast Substantial Completion is 2021-07-02 (27 critical activities); the as-planned date was 2021-06-30.
3. The same schedule is exported to P6 XER (CRLF line ends, cp1252, durations and lags in hours at 8 h/day, `PR_FS` etc.), MS Project MSPDI XML (activity ID in Text1 and UID = the number in the ID, summary tasks for the project and each WBS group, `LinkLag` in tenths of minutes = days x 4800), CSV and XLSX (with a `Predecessors` column like `A1010FS+2, A1020`, plus trailing Actual Start, Actual Finish and Remaining Duration columns), a printed Gantt PDF with no logic, and a CSV with no predecessors.
4. Each CP's `fragnet_truth` is run through `cpm_ref.tia` against the June 2020 update. The answer key's delay, `fragnet_critical`, `padded`, extension, compensability and cost all come from that run and from contract A's rules: extension only for non-contractor causes that delay the critical path (Section 3.4), capped at the days claimed; compensation only for Owner or Architect causes without concurrency, at $3,185 per day with no Fee (Sections 5.2 and 6.5.6). Claims marked "accurate" are set to the computed delay; other claims are fixed numbers, and the script asserts each case behaves as designed (critical, partly absorbed by float, or fully absorbed).
5. `contract_terms_key.json` holds the expected terms for both contracts. The script checks that every quote is a verbatim substring of its contract, that the value appears in the quote, that the section number is the paragraph holding the quote, and that each key number appears exactly once in contract B.

## Cases
| CP | Scenario | Cause | Claimed | Computed delay (cal / work) | Extension | Compensable | Expected cost | Split |
|---|---|---|---|---|---|---|---|---|
| CP-0401 | On critical path, Owner-caused, accurate claim | owner | 11 cal | 11 / 6 | 11 | yes | $35,035 | dev |
| CP-0402 | On critical path, Architect-caused, accurate claim | architect | 7 cal | 7 / 4 | 7 | yes | $22,295 | test |
| CP-0403 | On critical path, Owner-caused, claim stated in working days | owner | 7 work | 12 / 7 | 12 | yes | $38,220 | dev |
| CP-0404 | Off critical path (sitework float), Owner-caused, days claimed | owner | 14 cal | 0 / 0 | 0 | no | $0 | dev |
| CP-0405 | Off critical path (existing-building float), Architect-caused, days claimed | architect | 12 cal | 0 / 0 | 0 | no | $0 | dev |
| CP-0406 | Partial float consumption, Owner-caused, full event duration claimed | owner | 17 cal | 10 / 5 | 10 | yes | $31,850 | dev |
| CP-0407 | On critical path, Architect-caused, padded claim | architect | 21 cal | 7 / 4 | 7 | yes | $22,295 | test |
| CP-0408 | Partial float consumption, Architect-caused, padded claim | architect | 14 cal | 7 / 4 | 7 | yes | $22,295 | dev |
| CP-0409 | On critical path, contractor-caused (no extension) | contractor | 7 cal | 10 / 5 | 0 | no | $0 | dev |
| CP-0410 | Off critical path, contractor-caused, days claimed | contractor | 10 cal | 0 / 0 | 0 | no | $0 | test |
| CP-0411 | On critical path, weather (neither party), accurate claim | neither | 7 cal | 7 / 4 | 7 | no | $0 | dev |
| CP-0412 | Partial float consumption, weather (neither party), padded claim | neither | 21 cal | 7 / 4 | 7 | no | $0 | test |
| CP-0413 | Concurrent delay: Owner flooring change and flooring sub crew shortage | owner (concurrent) | 11 cal | 11 / 6 | 11 | no | $0 | dev |
| CP-0414 | No time claimed; work off the critical path | architect | 0 cal | 0 / 0 | 0 | no | $0 | dev |
| CP-0415 | No time claimed; no schedule impact | owner | 0 cal | 0 / 0 | 0 | no | $0 | test |

"Expected cost" is only the time-related cost (allowed compensable days x the contract A daily rate). The pricing sections are simple and tie out; every notice is on time, so the time question stands alone.

## Dev/test split
The split is fixed by `random.Random(20200601)` before anything is computed. The 15 cases are grouped into 5 strata of 3 (critical-path accurate claims; off-critical claims; padded or partial-float claims; non-compensable causes; concurrent or no claim), and one case per stratum is drawn as test. That gives 10 dev and 5 test cases, with every stratum in both. Tune prompts and rules on dev only.

## Conventions the answer key depends on
- Day numbering follows the spec: an activity with ES = day 0 and duration 5 occupies working days 0-4 and EF = 5; its finish date is working day 4. Milestones are dated on working day EF - 1 (day 0 for the start milestone), so Substantial Completion sits on the last working day of the work that drives it.
- `delay_workdays` is the change in the project's last EF; `delay_calendar_days` is the change in the finish date, so a one-working-day slip across a weekend or holiday counts 3 or 4 calendar days.
- In-progress activities keep their actual start; their remaining duration runs from the data date. Fragnet activities are not started and cannot start before the data date.
- Float is measured to the forecast finish, not to the contract date, so the 25 calendar days between the forecast and the contract date are not treated as available float.
- Weather is treated as outside the CM's control, so it earns time but not money; contract A does not mention weather, which is a judgment call (contract B's Section 3.5 does).

## Verification (from the last build)
- XER: 91 TASK, 142 TASKPRED, 21 holidays; relationships, durations and CPM finish 2021-07-02 match
- MSPDI XML: 91 tasks (+12 summary tasks), 142 links; CPM finish matches
- CSV: 91 rows, predecessors re-parse to the same 142 relationships; CPM finish matches
- XLSX: 91 rows identical to the CSV
- No-logic CSV: 91 rows, no Predecessors column
- PDFs: schedule.pdf text has all activity ids and no logic; contract_b.pdf text holds every quote's start
- Cases: 15 fragnets reference existing schedule ids, every F- activity appears in its narrative, and every answer-key delay re-computes
- CP PDFs written for dev cases CP-0401, CP-0404, CP-0406, CP-0413
- Contract B: 3130 words

## Limits
- **Same author.** The schedule, contract B, cases, narratives and answer key were written by our team, the same people building the tool. No independent scheduler or contract reviewer checked them.
- **One update.** Every TIA uses the single June 2020 update, even for events later in June. A real AACE 52R-06 analysis would use the update just before each event.
- **Simplified progress.** No out-of-sequence progress, no resource leveling, one calendar, no retained-logic vs. progress-override choice beyond the rule above.
- **Narratives are generated from the fragnets**, with a hand-written lead-in, so they are cleaner and more explicit than a real CM's time narrative.
- **Exports are hand-built**, not saved from P6 or MS Project. They follow the published table and element names, but a real tool may write fields we omit.
- **Contract A's weather and concealed-condition treatment** is not spelled out in that contract; our labels state the assumption above.
