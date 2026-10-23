# Demo 2 data note: 30 labeled architect and owner messages

## What this is
Thirty short messages of the kind an architect or owner sends a general contractor: RFI responses, ASIs, emails, submittal returns, and meeting-minute entries. Each has a received date, a label (**clarification** or **change**), and a one-sentence reason. Fifteen are clarifications and fifteen are changes. Ten of the thirty are marked `subtle`.

Files: `cases.json` (with labels), `cases_blind.json` (messages only, for independent labeling), `build_cases.py` (the generator and checks).

## Why it is synthetic
Real project correspondence is private, and we do not have a partner project. The Webster audit and board reports describe change orders but do not include the messages that led to them. The messages are written to match the synthetic contract from Demo 1 and the typical shape of school-project correspondence (Division 01 coordination, finish and equipment changes, code items, owner requests).

## How the cases were made
- **Balanced:** 15 and 15, so a classifier that always answers "change" scores 50%.
- **Mixed sources:** RFI responses, ASIs, emails from the Owner's Representative or Architect, a submittal return, and two meeting-minute entries (the contract says minutes are not notice, Section 7.7).
- **Subtle cases (10):** five clarifications that sound like instructions or added work, and five changes that are phrased politely or labeled "clarification" or "no cost impact". These test whether the classifier reads the substance and not the wording.
- **Dates:** weekdays across September 2019 to June 2020, plus one Saturday. Dates were chosen so that some notice deadlines fall on weekends or holidays (Veterans Day, Thanksgiving, Christmas, MLK Day, Presidents Day), which tests the contract's next-business-day rule.
- **Notice deadline:** for each change, the script computes the due date: 7 calendar days after receipt (Sections 6.2(a), 6.2(b), 6.8), moved to the next business day if it lands on a weekend or US federal holiday (Section 1.4). Clarifications have no deadline.

## Labeling rule
- **Clarification:** the message confirms or explains what the contract documents already require. Work, materials, quantities, sequence, and time are the same as the base contract.
- **Change:** the message requires work, materials, quantities, sequence, or time that differ from or go beyond the contract documents, so cost or time is likely to change.

The label describes the substance of the message, not whether a cost claim would succeed.

## Link to the thesis
Demo 2 tests the classification half of the thesis: that an agent can tell a clarification from a possible change at the handoff, and then start the contract's notice clock. Targets from the thesis: at least 85% label agreement, each label tied to a contract clause, and the correct notice deadline for every change.

## Limits
- The labels were written by one author and have not been checked by a second person. Before reporting results, have two teammates label `cases_blind.json` independently, compare to `cases.json`, and report the agreement.
- The same author wrote the contract and the cases, so the cases are cleaner than real correspondence. Real messages are longer, vaguer, and often mix a clarification with a change.
- Thirty cases is a small sample. One miss moves the score by about 3 percentage points.
- A few cases are arguable in practice (for example, a conflict between a drawing and a specification may be resolved in favor of the stricter document). The label here follows the stated rule above, and the reason column says why.
- Holidays are US federal holidays, which a real project may define differently.
