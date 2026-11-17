# Demo 3: ClauseStream, role agents on priced change proposals (INFO 492 C, Team 6)

Each party on a change runs its own agent: the **Subcontractor**, the **GC/CM**, the **Architect**, and the **Owner's PM**. Each one reviews a priced Change Proposal (CP) from its own seat and within its own authority, quotes the clause it relies on, and hands a message to the next party. People make every decision.

Live: [check tool](https://info492-team6.vercel.app/check/) (the product this demo led to) · [results with evaluation](https://info492-team6.vercel.app/demo3/) · [agent dashboard](https://info492-team6.vercel.app/app/)

**What came out of it.** The agents on free 8B models caught 22 of 33 seeded issues and flagged every clean proposal. Every check that is plain arithmetic, moved into code (`rules.py`), caught 23 of 33 with no false alarms. The same small model, asked only to *copy* numbers from a PDF (`extract.py`), read 121 of 121 fields right on five sample PDFs. So the check tool splits the work: the model reads, code checks, a person confirms. These follow-ups were designed after seeing the Demo 3 runs and are scored beside them, not in place of them.

## What it tests (thesis claim 3)
Can agents checking each handoff catch at least **85%** of seeded pricing and notice violations when the CP is submitted, rather than in a post-payment audit? They must do this without flagging clean CPs, and must send delay claims, site conditions, and amounts over the approval limit to a person.

## How it works
| Party | Sees | Owns | Authority |
|---|---|---|---|
| Subcontractor agent | Its own quote only | Markup limits, breakdown, T&M tags | Submit or hold; can't escalate |
| GC/CM agent | Full CP | Sub pricing, backup, tie-out | Send on, return to sub, escalate to the CM PM |
| Architect agent | Full CP plus scope context | Is it really a change? | Reviews for the Owner; can't approve cost or time |
| Owner's PM agent | Full CP | Fee, covered costs, equipment, burden, notice, claims | Recommend, return, or escalate; never approves |

- **Envelope.** Every handoff is a JSON envelope with envelope id, previous id, from, to, authority, decision, flags (type, section, quote, amount, explanation, quote verified), message, model, and time. The envelopes in order form the audit trail.
- **Integration.** Every agent gets Demo 1's extracted rule card (78 pricing and notice rules with verified quotes). Notice dates come from Demo 2's `deadlines.py`.
- **Agents judge; code computes.** `calc.py` adds up the cover sheet, works out markup and Fee percentages, and computes notice due dates. The agents decide which rules apply.
- **Baseline.** `baseline.py` runs the same calculator plus keyword lists copied from the contract, with no AI.

## Run it
```bash
pip install -r requirements.txt   # optional: only for PDFs, sample PDFs, or the Claude back end
python tests/test_demo3.py        # offline checks
python data/build_cases.py        # rebuilds cases.json and answer_key.json (deterministic)
python agents.py --dry-run
python agents.py --backend ollama --model llama3.1:8b   # free, local; or push RUN_LOCAL.txt to run on GitHub
python baseline.py && python rules.py && python evaluate.py
python hybrid.py --curve           # tradeoff of adding agent flags to the computed checks
node ../tools/parity.js           # browser checks (assets/checks.js) match rules.py on all 36 CPs
```
- **Cost.** About 140 calls at roughly 11k input tokens each.
- **Local model.** See `LOCAL_MODEL.md`.
- **Models.** Runs on open models through Ollama: Llama 3.1 8B (main) and Qwen2.5 7B (comparison). The `Demo 3 - local models` workflow runs them free on GitHub's runners in parallel jobs; `RUN_LOCAL.txt` lists the models. The same code runs on Claude with `--backend anthropic`.
- **Live mode.** `python3 serve_local.py` serves the whole site on your computer: the check tool's PDF upload (`/api/extract`) and the dashboard's "Run agents live" (`/api/demo3`) call Ollama there, with no key and no cost.

## Files
| Path | What |
|---|---|
| `data/build_cases.py` | Generates the 36 CPs and the answer key, and checks the labels against the date code |
| `data/cases.json`, `data/answer_key.json` | What the agents see; what the evaluation scores against |
| `data/DATA_NOTE.md` | Sources, method, and limits of the data |
| `prompts/` | Shared system prompt, one file per role, user template |
| `calc.py` | Calculator sheet (arithmetic and dates only) |
| `agents.py` | Role views, API and Ollama back ends, envelopes, audit trail, batch runner |
| `baseline.py` | No-AI comparison |
| `evaluate.py` | Detection, responsible-party catches, routes, false alarms, escalation, citation validity |
| `results/` | Runs and evaluation |
| `serve_local.py` | Site plus live agents on your own computer (Ollama) |
| `merge_runs.py` | Merges the parallel GitHub jobs into one run per model |
| `rules.py` | The computed checks with the arithmetic shown (pre-check sheet); scored as its own system |
| `hybrid.py` | Tradeoff table: computed checks plus agent flags at different strictness |
| `extract.py` | Reads a PDF's text into the check form with the local model; `--test` runs the sample PDFs |
| `../assets/checks.js` | The same checks in the browser, for the check tool |
| `../check/` | The check tool: upload, confirm the numbers, marked-up result |
| `../app/` | Sign-in with role selection, and the agent dashboard (Demo 3 research) |

## Targets (set before running)
- At least 85% of the 33 seeded issues caught.
- Clean CPs not flagged.
- Every quote verified in the contract.
- All 6 escalations routed to a person.

Do not change the cases, labels, prompts, or targets after seeing results. Record any rerun as Run 2.
