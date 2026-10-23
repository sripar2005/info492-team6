# Demo 2: Change Classifier (INFO 492 C, Team 6)

Demo 2 tests the next step of our thesis. When the general contractor (CM) receives an RFI response, ASI, submittal return, owner email, meeting minutes, field report, or third-party letter, can an AI agent tell whether it is a **clarification** or a **possible change**, cite the contract clause that decides it, and get the **notice deadline** right?

This is the first handoff in our thesis (RFI answer → change notice). Missing it is how contractors lose money: under Section 6.2 of the contract, notice that is late waives the cost incurred before notice.

## What changed since Demo 1

- **Demo 1 asked:** can the contract's rules be extracted at all? Result: 94.4% of core rules, every quote real.
- **Demo 1's main gap:** rules that say "give notice under Section 6.2(a)" were extracted without the 7-day deadline that 6.2(a) sets. A checker built on that would miss the clock.
- **Demo 2 tests that gap directly:** every possible change must be traced to one Section 6.2 rule, often through a cross-reference (ASI → 6.8 → 6.2(a); submittal comment → 8.3 → 6.2(a); meeting minutes → 7.7, not notice).
- **New design choice:** the model picks the rule; **code computes the date** (`deadlines.py`, including Section 1.4's weekend and holiday roll-forward). We score the model's own date and the code date side by side, to test whether splitting the work this way is more reliable.

## Measures and targets (set before running)

| Measure | Definition | Target |
| --- | --- | --- |
| Label accuracy | correct clarification / possible change, out of 30 | **at least 85%** (thesis claim 4) |
| Change recall | real changes the agent flagged | report (a miss can forfeit payment) |
| Change precision | flags that were real changes | report (false alarms cost review time) |
| Notice rule accuracy | right 6.2 (a)/(b)/(c)/(d), on flagged real changes | report |
| Deadline accuracy | model's own date vs code-computed date | report both |
| Citation validity | quote found word for word in the contract | report (aim 100%) |
| Tricky-case accuracy | the 11 cases built to mislead | report |

Do not change the targets, the cases, the labels, or the prompts after seeing results. If anything changes, record it as a new run.

## Run it

```bash
pip install -r requirements.txt
python tests/test_pipeline.py        # offline checks, no API calls
python data/build_cases.py           # rebuilds cases.json and answer_key.json (deterministic)
python classifier.py --dry-run       # 30 documents, 1 call each
export ANTHROPIC_API_KEY=your_key    # or run the GitHub workflow "Demo 2 - run classifier"
python classifier.py
python evaluate.py                   # writes results/evaluation_report.md
```

Cost: about 6,000 input tokens per document (the contract is sent each time), about 180,000 input tokens per run. Responses are cached in `results/cache/`.

## Files

| Path | What it is |
| --- | --- |
| `data/build_cases.py` | **Generation script.** Defines the 30 documents and labels; computes every notice due date from the rule |
| `data/cases.json` | What the model sees: type, sender, event date, text. No labels |
| `data/answer_key.json` | Labels, rule, sections, due date, why, tricky flag. Read only by `evaluate.py` |
| `deadlines.py` | Section 6.2 periods and Section 1.4 roll-forward as code |
| `prompts/classify_system.txt`, `prompts/classify_user.txt` | The prompts, exactly as used |
| `classifier.py` | Calls Claude once per document through the `record_classification` tool; verifies quotes; computes code dates |
| `evaluate.py` | Scores the run; writes a per-case trace for the website |
| `tests/test_pipeline.py` | Offline tests of deadlines and scoring |
| `results/` | Run outputs |

The contract is Demo 1's synthetic contract (`../demo1/data/synthetic_contract.md`), unchanged.

## Data justification (synthetic documents)

Real RFI logs, ASIs, and owner correspondence for public school projects are not published; getting them takes a public records request. We wrote 30 short documents in the style of the ones a CM receives, set on the same synthetic contract as Demo 1 (modeled on Seattle Public Schools' Webster School GC/CM project).

- **Balance:** 15 clarifications, 15 possible changes; 7 under 6.2(a), 4 under 6.2(b), 2 under 6.2(c), 2 under 6.2(d).
- **Variety of sources:** RFI responses, ASIs, submittal returns, owner emails, daily-log oral directions, meeting minutes, field reports, a building department notice, and a utility letter.
- **11 tricky cases built to mislead:** an ASI marked "no change in cost or time" that adds work (and one that truly doesn't); a submittal rejection that only enforces the spec versus one that adds work beyond it; an owner email asking for upgrade ideas while saying "don't proceed"; a change mentioned only in meeting minutes; an oral direction; a concealed condition found on a Saturday; and an RFI response whose deadline lands on Memorial Day.
- **Deadlines are computed, not typed:** `build_cases.py` computes each due date from the event date and rule, and checks that only the two designed cases roll forward.
- **2020 Washington State legal holidays** are used for the roll-forward rule.

## Limits

- The documents and labels were written by the same author as the contract, and have not yet been independently labeled by a teammate. A second person labeling the same 30 documents would give us a human agreement baseline.
- 30 documents on one synthetic contract is a small, controlled test, not a field result.
- Real documents are messier: attachments, drawings, email threads, and partial information.
- Without a temperature setting (removed in the current Anthropic SDK), a re-run may differ slightly; the committed `results/` files are the record.
