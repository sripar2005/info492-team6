# Demo 4 spec: own contract, schedules, delay checks

Shared interfaces for the Demo 4 build. Everything here is synthetic test data or code; no API keys, no paid calls.

## 1. Schedule model (one format inside the tool)

Every uploaded schedule (P6 XER, MS Project XML, Excel/CSV, PDF) is converted to this JSON:

```json
{
  "name": "Webster-style school modernization (synthetic)",
  "data_date": "2020-06-01",
  "start": "2020-02-03",
  "calendar": { "workdays": [1,2,3,4,5], "holidays": ["2020-05-25", "..."] },
  "activities": [
    { "id": "A1000", "name": "Notice to Proceed", "duration": 0, "wbs": "Milestones",
      "actual_start": null, "actual_finish": null, "remaining": null,
      "constraint": null }
  ],
  "relationships": [ { "pred": "A1000", "succ": "A1010", "type": "FS", "lag": 0 } ],
  "source": { "format": "xer", "file": "school.xer", "has_logic": true }
}
```
- `duration`, `remaining`, `lag` are in working days. `type` is FS, SS, FF or SF.
- `constraint` is null or `{ "type": "SNET" | "FNLT" | "MSO" | "MFO", "date": "YYYY-MM-DD" }`.
- Dates are ISO `YYYY-MM-DD`. Day numbering: an activity with ES = day 0 and duration 5 occupies working days 0-4; EF = 5 (exclusive end), shown as finish date = date of working day 4.
- `source.has_logic` is false when relationships could not be read (PDF, most CSVs); then the critical path is "not verifiable".

## 2. Schedule engine API (`assets/schedule.js`, UMD like `assets/checks.js`)

- `parseXER(text)`, `parseMSPDI(xmlText)`, `parseCSV(text)`, `parseRows(rows)` (for Excel, rows from SheetJS) → schedule model
- `cpm(schedule)` → `{ activities: [{id, es, ef, ls, lf, total_float, critical, start, finish}], finish_date, critical_path: [ids in order], warnings: [...] }`
- `quality(schedule)` → list of `{ check, severity: "warn"|"info", count, ids, note }`: missing predecessors/successors (open ends), negative lags, hard constraints, durations over 44 working days, relationships to missing activities, cycles.
- `tia(schedule, fragnet)` → AACE 52R-06 style prospective time impact:
  `{ before_finish, after_finish, delay_workdays, delay_calendar_days, fragnet_critical: bool, driving_path: [ids], notes }`.
  `fragnet = { activities: [{id, name, duration}], relationships: [{pred, succ, type, lag}] }`; fragnet ids start with `F-`.
- Calendar arithmetic honors `calendar.workdays` and `calendar.holidays`.

## 3. Contract terms (what "load your own contract" extracts)

```json
{
  "name": "Sample GC/CM contract",
  "terms": {
    "markup_own_pct":        { "value": 10, "quote": "...", "section": "6.5.2" },
    "markup_lower_pct":      { "value": 5 },
    "markup_total_pct":      { "value": 15 },
    "fee_pct":               { "value": 5 },
    "fee_allowed_on":        { "value": ["CM direct costs", "subcontractor quotes"] },
    "labor_burden_pct":      { "value": 32 },
    "blue_book_pct":         { "value": 75 },
    "approval_limit":        { "value": 250000 },
    "notice_days_by_cause":  { "value": { "RFI response": 7, "ASI": 7, "Submittal return": 7, "Owner direction": 7,
                                          "Architect direction": 7, "Concealed condition": 7, "Other event": 14 } },
    "contract_days":         { "value": 540 },
    "liquidated_damages_per_day": { "value": 2500 },
    "daily_delay_rate":      { "value": 3185 },
    "sgc_total":             { "value": 1720000 },
    "extension_requires_critical_path": { "value": true },
    "compensable_causes":    { "value": ["owner", "architect"] },
    "concurrent_delay":      { "value": "time_no_money" }
  }
}
```
Every term carries `quote` (verbatim from the contract) and `section`. Code verifies the quote appears in the contract text and the value appears in the quote; otherwise the field is marked "check this".

## 4. Change orders with a time section (Demo 4 cases)

Same shape as `demo3/data/cases.json`, plus:
```json
"time": { "claimed_days": 12, "claimed_calendar": true, "narrative": "...", "cause_party": "owner" | "architect" | "contractor" | "neither",
          "concurrent": false },
"fragnet_truth": { "activities": [...], "relationships": [...] }
```
Answer key per case: expected `delay_calendar_days` (from TIA), `fragnet_critical`, `padded` (claimed > computed), `compensable`, `expected_cost` under the contract, and `split`: "dev" or "test".

## 5. Files
- `assets/schedule.js`, `tools/schedule_test.js`: schedule engine and its tests
- `demo4/data/`: synthetic schedule in every format, second synthetic contract, change orders, answer keys
- `demo4/cpm_ref.py`: independent Python CPM/TIA used to build the answer key (cross-checks the JS engine)
