# Platform sample data: what to produce

Synthetic data for the shared platform: companies, the contract chain, subcontracts, a schedule of values, schedule updates, and each sub's change requests. It extends the existing synthetic school project. Everything here is synthetic and written with AI assistance for INFO 492 C coursework. No real firm, person or project.

## Inputs to read (data only)
- `record/bundle.json` (the project record: 182 documents, their pieces and links)
- `demo1/data/synthetic_contract.md` (the prime contract, "contract A", Owner and GC/CM, a GC/CM contract)
- `demo3/data/cases.json` and `demo4/data/cases.json` (change proposals with `subcontractor_quotes`)
- `demo4/data/schedule.json` and `demo4/data/DATA_NOTE.md` (the schedule as of the 2020-06-01 update)

Do not open any code under `assets/`, `demo4/*.py` other than to run nothing, or `record/*.py`. The data is used to test that code, so it must be written without looking at it.

## Outputs (all under `record/platform/`)

### `platform.json`
```jsonc
{
  "meta": {"synthetic": true, "note": "...", "built": "2026-11-..."},
  "project": {"name": "...same as bundle...", "contract_type": "gccm"},   // gccm | hard_bid | design_build
  "companies": [
    {"key": "owner", "name": "Example School District No. 1", "kind": "owner"},
    {"key": "architect", "name": "...", "kind": "architect"},
    {"key": "gc", "name": "...", "kind": "gc"},
    {"key": "sub-cascade-plumbing", "name": "Cascade Plumbing", "kind": "sub", "trade": "Plumbing"}
    // one per distinct subcontractor firm in the cases (and lower-tier firms as kind "sub" with "tier": 2 and "parent": the sub's key)
  ],
  "contracts": [
    {"key": "prime", "kind": "prime", "up": "owner", "down": "gc", "parent": null, "title": "...", "document_key": "<bundle key of the contract document>", "terms": []},
    {"key": "design", "kind": "design", "up": "owner", "down": "architect", "parent": null, "title": "...", "file": "record/platform/docs/design_summary.md", "terms": [...]},
    {"key": "sub-cascade-plumbing", "kind": "sub", "up": "gc", "down": "sub-cascade-plumbing", "parent": "prime", "title": "...", "file": "record/platform/docs/subcontract_cascade_plumbing.md", "terms": [...]}
  ],
  "sov": [
    {"contract": "prime", "code": "01-100", "description": "...", "amount": 0, "general_conditions": true, "basis": "time"}  // time-based general conditions lines, plus non-time lines
  ],
  "schedule_versions": [
    {"key": "baseline", "label": "Baseline", "data_date": "2020-02-03", "file": "record/platform/schedule_baseline.json", "caused_by": null},
    {"key": "u1", "label": "Update 1", "data_date": "2020-06-01", "file": "demo4/data/schedule.json", "caused_by": null},
    {"key": "u2", "label": "Update 2", "data_date": "...", "file": "record/platform/schedule_u2.json", "caused_by": ["CP-04xx"]}
  ],
  "sub_requests": [
    {"key": "CR-...", "number": "...", "change": "CP-0212", "from": "sub-...", "to": "gc", "submitted": "YYYY-MM-DD",
     "amount": 0.0, "days": 0, "narrative": "plain words, as the sub's PM would write it",
     "lines": [{"desc": "...", "amount": 0.0}], "lower_tier": [{"firm": "...", "amount": 0.0}]}
  ],
  "field_samples": [ {"from": "sub-...", "text": "a foreman's raw text, typos ok", "name": "first name only", "becomes": "CP-.... or null"} ]
}
```

Terms use the same shape for every contract: `{"key": "notice_days", "value": 7, "clause": "§ 4.2", "sentence": "exact sentence from the document"}`. Keys to cover in each subcontract: `notice_days` (the sub's own notice window), `notice_flowdown` (whether prime-contract notice terms flow down, true/false), `markup_own`, `markup_lower_tier`, `pricing_days` (days to price a change after a request), `pay_if_paid` (true/false), `delay_compensable` (text: who pays for delay). Every `sentence` must appear word for word in that contract's file, and the value must appear in the sentence.

### Contract files
- One markdown subcontract per sub in `record/platform/docs/`, short (about 1 to 2 pages), each with a flow-down clause, a notice clause, a markup clause, a pricing-time clause, and payment terms. Vary them: at least two subs must have a notice window that leaves the GC too little time to pass notice up under prime contract § 6.2 (a "flow-down gap"), and at least one must be clean.
- `design_summary.md`: a short summary of the Owner and Architect agreement, including the architect's review times for RFIs and submittals.

### Schedule files
- `schedule_baseline.json`: the as-planned schedule before progress (same format as `demo4/data/schedule.json`; no actuals).
- `schedule_u2.json`: a later update after at least one compensable delay from `demo4/data/cases.json` was accepted, same format, with a later data date and the fragnet activities added.

### `answer_key.json`
What correct software should find, computed independently with your own scripts (you may write and run Python under `record/platform/build/`):
- `flowdown_gaps`: for each sub, whether its notice window leaves the GC time to meet the prime contract's notice window, and by how many days.
- `cost_per_day`: the time-based general conditions cost per calendar day from the SOV, and the prime contract's stated daily rate, and whether they agree.
- `rollups`: for each change in `sub_requests`, the sum of its sub requests and how that compares with the change's `subcontractor_quotes` total in the cases.
- `visibility`: for each company key, which `sub_requests` keys it should see under this rule: a sub sees only its own requests; the GC/CM sees all requests sent to it; the owner and architect see none (they see the GC/CM's proposal, which lists the request numbers and amounts but not the sub's lines).

### `DATA_NOTE.md`
How it was built, what is synthetic, and every deliberate quirk (the flow-down gaps, any mismatches).

## Rules
- Use the firms already named in the cases; invent the owner's architect and GC/CM names only if the bundle doesn't name them (check the bundle's documents first).
- Amounts in `sub_requests` must match the cases' `subcontractor_quotes` for the same change unless you mark a deliberate mismatch in the answer key.
- Write a script `record/platform/build/build.py` that regenerates every output and asserts the checks above. Run it until it passes.
