# Demo 3: ClauseStream, role agents on priced change proposals (INFO 492 C, Team 6)

Each party on a change runs its own agent: the **Subcontractor**, the **GC/CM**, the **Architect**, and the **Owner's PM**. Each one reviews a priced Change Proposal (CP) from its own seat and within its own authority, quotes the clause it relies on, and hands a message to the next party. People make every decision.

Live: [landing](https://info492-team6.vercel.app/clausestream/) → [sign in with a role](https://info492-team6.vercel.app/app/) → [dashboard](https://info492-team6.vercel.app/app/dashboard.html) → [results with evaluation](https://info492-team6.vercel.app/demo3/)

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
pip install -r requirements.txt
python tests/test_demo3.py        # offline checks
python data/build_cases.py        # rebuilds cases.json and answer_key.json (deterministic)
python agents.py --dry-run
python agents.py --backend ollama --model llama3.1:8b   # free, local; or push RUN_LOCAL.txt to run on GitHub
python baseline.py && python evaluate.py
```
- **Cost.** About 140 calls at roughly 11k input tokens each.
- **Local model.** See `LOCAL_MODEL.md`.
- **Models.** Runs on open models through Ollama: Llama 3.1 8B (main) and Qwen2.5 7B (comparison). The `Demo 3 - local models` workflow runs them free on GitHub's runners in parallel jobs; `RUN_LOCAL.txt` lists the models. The same code runs on Claude with `--backend anthropic`.
- **Live mode.** `python3 serve_local.py` serves the whole site on your computer, and the dashboard's "Run agents live" calls Ollama there, with no key and no cost. `vercel_api.py` is an optional, undeployed Claude endpoint.

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
| `vercel_api.py` | Optional Claude endpoint, not deployed |
| `../app/` | Sign-in with role selection, and the role dashboard |

## Targets (set before running)
- At least 85% of the 33 seeded issues caught.
- Clean CPs not flagged.
- Every quote verified in the contract.
- All 6 escalations routed to a person.

Do not change the cases, labels, prompts, or targets after seeing results. Record any rerun as Run 2.
