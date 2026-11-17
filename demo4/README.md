# Demo 4: your contract, your schedule, the delay

After the Nov 17 meeting with an owner-side project manager (Lake Washington School District, 30+ years), the check tool takes three new steps:

1. **Load your own contract.** The markup, fee, labor, equipment, approval, notice and delay terms are read from the contract, each tied to the sentence it came from. A person confirms each term before the checks use it.
2. **Load your schedule.** Primavera P6 `.xer`, Microsoft Project `.xml`, Excel, CSV or PDF. The critical path is recomputed from the logic in the file, with schedule quality checks, edits, and baseline/update versions.
3. **Check a delay.** The change's work is inserted into the current schedule as a fragnet and the critical path rerun (a time impact analysis in the style of AACE 52R-06). The days are then priced under the contract, with toggles for who caused the delay, paid vs time-only, and concurrent delay.

All of it is on the check page: `/app/#contract`, `/app/#schedule`, `/app/#delay`.

## Who does what

| Step | Code | AI (local model) | Person |
|---|---|---|---|
| Contract terms | Splits the contract into sentences; finds the few candidate sentences per term; checks the value is in the chosen sentence | Picks one candidate sentence per term, or "not stated" (it can't cite anything else); reads 3 times | Confirms or fixes each term |
| Schedule | Parses every format; CPM; quality checks | — | Sets the calendar for formats that lack one; edits |
| Fragnet | Shortlists the schedule activities; drops links that don't fit | Drafts the change's activities, linking only to listed activity IDs; drafts 3 times | Confirms or edits the fragnet |
| Delay and cost | Time impact analysis; extension, paid days, rate, flags | Never computes days or dollars | Sets the conditions; confirms the result; optionally saves a schedule update |

Every step on the delay check is written to an audit log tagged *AI proposed*, *Computed* or *Person*, and the log can be exported.

## How we keep the AI honest

- **Choose, don't write.** The model's output is constrained to the real options: sentence IDs from the contract, activity IDs from the schedule.
- **Prove it with a quote.** Code checks that each value appears in its quoted sentence. If it doesn't, the term is marked "check this".
- **Fixed procedure in code.** CPM, the time impact analysis and the contract pricing are deterministic code, tested by hand-computed cases.
- **Agreement.** The model reads or drafts three times. If the readings disagree, the person is told to look closer.
- **Dev/test split.** Keywords and prompts were tuned on contract A and the dev change orders only. Contract B and the five test change orders are held out and reported separately.
- **Two engines.** The browser engine (`assets/schedule.js`) and an independent Python reference (`demo4/cpm_ref.py`) were written separately and agree on every check.

## Tests (no model needed)

```
node tools/schedule_test.js      # 143 hand-computed CPM/TIA/parser checks
node tools/tia_crosscheck.js     # JS engine vs the Python reference: all formats, all 15 change orders
node tools/delay_test.js         # delay pricing rules + the 15-case answer key (extension, paid, cost, padded)
node tools/contract_parity.js    # browser sentence search = Python sentence search, contracts A and B
python3 demo4/cpm_ref.py         # 34 reference self-tests
python3 demo4/contract_extract.py --retrieval-test   # the right sentence is among the candidates: A 17/17, B 17/17
```

## Model tests (free, on GitHub)

Actions → **Demo 4 model test** → Run workflow, once per model. This runs `demo4/contract_test.py` and `demo4/fragnet_test.py` with Ollama on the GitHub runner and commits the results to `demo4/results/`. The site replays the saved runs, so the demo does not need a model running.

Results: see `demo4/results/` (filled in as runs finish).

## Data

All synthetic, written by our team with AI assistance (see `demo4/data/DATA_NOTE.md`):

- the 91-activity school modernization schedule in six formats, plus a version with no logic;
- contract B, with different terms and distractor numbers;
- 15 change orders with time claims covering on and off the critical path, padded claims, claims in working days, contractor-caused, weather and concurrent delay.

## Limits

- **The data is synthetic and labeled by the same team.** No one independent has checked it yet. Three outputs go to our stakeholder for expert review.
- **The narratives are cleaner than real ones.** They name the activity IDs the change ties to, which makes the fragnet drafter's job easier than in practice.
- **Scheduling simplifications.**
  - One calendar per schedule; whole days only.
  - `.mpp` must be saved as XML first.
  - A PDF schedule has no logic, so its critical path can't be verified, and the tool says so.
- **Analysis scope.** Delay is measured against the forecast finish, using one schedule update. There is no windows analysis across updates.
- **Pricing.** A daily rate stated in the contract governs. When the contract states none, general conditions ÷ contract days is used. These are not the only accepted methods.
- **Storage.** Contracts and schedules are stored in the browser only.
- **Not yet built.** Procore integration and real district data (public records request) are next.
