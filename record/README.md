# Project record (synthetic)

> **SYNTHETIC AND AI-ASSISTED.** Everything in this folder is invented test data for INFO 492 C coursework, drafted with AI assistance and checked by script. No real project, firm, person, or document is represented. Every document carries `source: "synthetic"` and the project carries `synthetic: true`.

## What this is

ClauseStream's shared project record: the documents of one construction project (a public school modernization and addition in Washington State, GC/CM delivery under contract A) split into small citable **pieces**. Every party (sub, GC/CM, architect, owner's rep) checks change proposals and RFIs against the same pieces. The record is the seed data for the tables in `supabase/migrations/0001_project_record.sql` (`documents`, `pieces`, `links`).

We do not yet have real project documents (a public-records request for real RFI logs is in progress). This set lets us build and test now, and is designed to be **swapped one document at a time** for real ones.

It is consistent with the existing demo data, which it reads but never changes:

| Source | Used for |
|---|---|
| `demo1/data/synthetic_contract.md` | Contract A, split into one piece per clause (text verbatim, markdown emphasis removed) |
| `demo3/data/cases.json` | CP-0201 to CP-0236: one change-order document each, and the RFIs, ASIs, submittal, owner emails, field reports, and letters they cite |
| `demo4/data/cases.json` | CP-0401 to CP-0415, with time narratives; fragnet ties become `affects` links to schedule activities |
| `demo4/data/schedule.json` / `schedule.csv` | The schedule document (one piece per activity) and the work named in daily reports |

## Build

```
python3 record/build_record.py
```

Standard library only, fixed seed, no timestamps: re-running gives byte-identical output. The script rebuilds `record/bundle.json` and `record/docs/` and runs a self-check (it exits non-zero on any failure):

- every cause reference in every demo3/demo4 case resolves to a document in the bundle;
- every link endpoint exists, and every `from_section` / `to_section` matches a real piece;
- RFI answer dates equal the case event date (so are on or before it), ASI and submittal-return dates equal the case event date, and cause documents predate the CP;
- daily reports fall on working days inside the schedule span (2020-02-03 to 2021-07-02), and every activity they name `Name (Axxxx)` matches `schedule.json`;
- minutes are approved, and only discuss documents already issued (or CPs whose event has happened);
- every piece body is non-empty, every party is one of `sub, gc, architect, owner`, and every contract piece is verbatim from the contract.

## Contents

| Kind | Count | Notes |
|---|---|---|
| contract | 1 | `Contract A`; sections like `6.5.3`, `Exhibit C`, `Exhibit E 01 26 00` |
| spec | 6 | 01 26 00, 02 82 00, 07 62 00, 08 71 00, 09 22 16, 22 14 26; pieces by paragraph (`2.03.B`) |
| rfi | 24 | the 12 cited by cases plus 12 that never became changes; pieces Question, Suggested solution, Answer |
| asi | 15 | the 11 cited by cases plus 4; pieces Description, Drawings/specs affected, Issued by |
| submittal | 10 | including `09 22 16-02` (Approved as noted, 18-gauge studs at the gym) |
| daily_report | 47 | 44 superintendent daily reports `DR-YYYY-MM-DD` plus field reports FR-12, FR-33, FR-41 |
| minutes | 7 | approved OAC minutes only (product rule); header piece states where they were approved |
| schedule | 1 | `SCH-2020-06-01`, `meta.file` points at `demo4/data/schedule.json` |
| change_order | 51 | one per CP (author gc), pieces Description, Cause, Amount requested, Time requested |
| other | 20 | correspondence that cases cite: owner emails/letters (`OE-`/`OL-<date>`), field order FO-07, notice letter NL-09, two subcontractor letters, permit record |

Link relations: `answered_by` (RFI to ASI), `caused_by` (CP to its cause), `cites` (CP/RFI/submittal to contract clauses and spec paragraphs), `supersedes` (ASI to spec paragraph), `evidence_for` (daily report to CP), `discussed` (minutes item to RFI/ASI/CP/etc.), `affects` (demo4 CP to schedule activity).

## Bundle format (`bundle.json`)

This is the import format the app loads. Keep it exactly.

```
{ "project": {"name": "...", "owner_org": "...", "synthetic": true},
  "documents": [ {"key": "RFI-112", "kind": "rfi", "number": "RFI-112", "title": "...", "issued_on": "2020-02-03", "author_party": "gc",
                  "source": "synthetic", "external_id": "syn:RFI-112", "file": "record/docs/rfi/RFI-112.md",
                  "meta": {...}, "pieces": [ {"ordinal": 1, "section": "Question", "body": "...", "piece_date": "2020-02-03", "party": "gc"}, ... ] } ],
  "links": [ {"from": "RFI-112", "to": "ASI-007", "relation": "answered_by", "from_section": "Answer", "to_section": null, "note": "..."} ] }
```

- `kind` is the schema's `doc_kind` enum; `party` and `author_party` are `sub`, `gc`, `architect`, `owner`.
- `key` equals `number` and is unique across the bundle. `from` / `to` are keys; `from_section` / `to_section` optionally pin one piece by its `section`.
- `file` is the readable copy under `record/docs/<kind>/`. File names are the number with spaces replaced by `_` (`Section 09 22 16` becomes `Section_09_22_16.md`). Each file starts with a one-line synthetic notice.

## Replacing a synthetic document with a real one

1. Keep the same `number` (for example `RFI-112`), so links and cases still find it.
2. Load the real document with `source` set to `upload` (or `procore` when synced, with the Procore id as `external_id`), split into pieces with the same section names where they apply (`Question`, `Answer`, paragraph numbers, activity ids).
3. Drop the synthetic file: add the number to `REPLACED` at the top of `build_record.py` and re-run. The document is left out of `bundle.json` and `record/docs/`, while links to it stay in the bundle and resolve to the real document by number on import.
4. If the real document's piece sections differ from the synthetic ones, update the links that pin a section (`from_section` / `to_section`) in the generator, so imports do not point at a missing piece.

## Known limits

- **Same authors.** The documents, cases, and checks were written by the team building the tool (with AI help); no outside CM, architect, or owner reviewed them.
- **Numbering is inherited.** RFI and ASI numbers come from the demo cases, which were written independently, so numbers are not in date order (RFI-171 is answered 2020-03-02, RFI-131 on 2020-06-01).
- **Daily report work comes from the June 2020 schedule update.** Reports after the data date list the work the forecast shows for that day; the as-built slips implied by later CPs (for example roofing still under way in November 2020 for CP-0227) are stated in the issues text, not re-scheduled.
- **One owner email can carry several directions.** demo3 and demo4 both cite "Owner email 2020-06-08" and "Owner email 2020-06-29" for different changes; each email is one document with one piece per direction, and each CP's `caused_by` link pins its piece.
- **Submittal actions** use contract A's wording (Section 8.3: "Approved as Noted", "Revise and Resubmit") plus "No exceptions taken" and "Rejected".
- Correspondence (owner emails and letters, field order, letters, permit) uses kind `other`, which the schema's `doc_kind` enum allows.
