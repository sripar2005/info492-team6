# Demo 3 data note

## What it is
36 priced Change Proposals (CPs) for a public school modernization run as GC/CM, written against Demo 1's synthetic contract (`../demo1/data/synthetic_contract.md`, modeled on Seattle Public Schools' Webster School project). Each CP is the package all four parties see:
- the cause (RFI response, ASI, submittal return, direction, concealed condition, or other event) and its date
- the notice date and submission date
- subcontractor quotes, either as structured line items or, in 6 cases, as the free-text email a sub actually sends
- the CM's own lines (labor with burden, equipment with Blue Book rates, materials, permit, bond, B&O tax, NSS)
- a cover sheet with markups and Fee
- scope context (what the drawings and specs say)
- the backup attached

## How it was made
`build_cases.py` builds every CP from its lines, so every cover sheet ties out unless a case deliberately breaks it. Issues are seeded by changing one input: a markup rate, a line that shouldn't be billed, an unsigned tag, a late notice date, or a cover-sheet adjustment. The script checks its own labels:
- Late-notice labels must match Demo 2's deadline code (Section 6.2 plus the Section 1.4 weekend and holiday roll-forward, using 2020 Washington State holidays).
- The over-$250,000 label must match the total.
- Every escalation type must have the route ESCALATE.

## What's in it
| Group | CPs | What it tests |
|---|---|---|
| Clean | 10 | Follows the contract; includes a deductive change, permit/bond/tax correctly without Fee, and keyword traps ("superintendent" and "crane" in a narrative, a sub's material "pickup") |
| One issue | 15 | Sub markup, Fee rate, Fee on excluded items, covered costs, equipment, labor burden, tie-out, missing backup, late notice, not a change |
| Escalation | 3 | Delay claim, concealed soils, amount over the $250,000 approval limit |
| Mixed | 4 | Several issues in one CP, like the Webster findings (Fee on NSS, equipment at full Blue Book, SGC staff billed) |
| Email quotes | 6 | The sub's quote arrives as text, so the calculator can't parse it |

There are 33 seeded issues in total. Expected routes: 10 approve, 20 return, 6 escalate. 12 cases are marked tricky.

## Why these issues
- **The Webster audit** questioned equipment add-ons, Fee on NSS above the contract rate, and items the Fee already covered.
- **The owner-side PM we interviewed** described his review order: cover sheet, backup, markups, then scope. He said he pushes back on subcontractor markups over the contract limit, and that delays and site conditions are the hard, contested part.
- **The pricing rules** come from the contract: Sections 5.2–5.5, 6.2, 6.3, 6.5.1–6.5.7, and Exhibits B–D.

## Limits
- **Same author.** The CPs, labels, prompts, and baseline keyword lists were all written by our team, the same people who wrote the contract and the agents. That favors what we expected. No independent labeler checked this set.
- **Simplified documents.** Real CPs are PDFs with drawings, photos, and email threads. Only 6 of ours have unstructured quotes.
- **Synthetic names.** All firm and person names are made up.
