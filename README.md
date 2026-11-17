# ClauseStream · INFO 492 C, Team 6

Yousuf Shaik, Sriharshith Paruchuri, Nithika Yechuri · University of Washington Information School, Autumn 2026

**Thesis.** An agent that checks each construction handoff (RFI answer → change notice → priced proposal → change order) against the contract can catch rule violations when the paperwork is submitted, instead of in a post-payment audit. People make every decision. Project lens: the Webster School audit (Seattle Public Schools, 2023).

**Site:** https://info492-team6.vercel.app/

| Page | What |
|---|---|
| [`/`](https://info492-team6.vercel.app/) | Landing page. The only page that links to the research |
| [`/app/`](https://info492-team6.vercel.app/app/) | **The product**: shared project record, change threads, contract, schedule and delay checks. Opens on its own; `/app/?project=sample` opens the sample project (synthetic, runs in the browser, nothing saved) |
| [`/research/`](https://info492-team6.vercel.app/research/) | Research hub: thesis, demo results, sources, log, agent dashboard |
| [`/thesis/`](https://info492-team6.vercel.app/thesis/), [`/demos/`](https://info492-team6.vercel.app/demos/), [`/demo1/`](https://info492-team6.vercel.app/demo1/)–[`/demo3/`](https://info492-team6.vercel.app/demo3/), [`/log/`](https://info492-team6.vercel.app/log/), [`/sources/`](https://info492-team6.vercel.app/sources/) | Research pages, linked from `/research/` |
| [`/research/agents/`](https://info492-team6.vercel.app/research/agents/) | Demo 3 agent dashboard with role sign-in (was `/app/`) |

Old links redirect (`vercel.json`): `/check/` → `/app/`, `/clausestream/` → `/`, `/app/dashboard.html` → `/research/agents/dashboard.html`.

## Repo
| Folder | What |
|---|---|
| `demo1/` | Rules extractor: pulls a contract's notice, pricing and fee rules into a citable rule card |
| `demo2/` | Change classifier: clarification or change, which notice rule, and the deadline (`deadlines.py`) |
| `demo3/` | Role agents on priced change proposals, the computed checks (`rules.py`), the PDF reader (`extract.py`), evaluation, and `serve_local.py` |
| `app/`, `assets/checks.js`, `assets/app.js` | The check tool; `app/samples/` holds synthetic sample PDFs |
| `app/`, `clausestream/`, `index.html` and the other folders | Site pages |
| `tools/` | Parity test between browser and Python checks, sample PDF generator, PDF reader scoring |
| `docs/` | Class feedback |
| `.github/workflows/` | Free runs on GitHub's machines: demo runs on local models, the PDF reader test |

## Run it locally
```bash
python3 demo3/tests/test_demo3.py     # offline tests
node tools/parity.js                  # browser checks match Python on all 36 test proposals
python3 demo3/serve_local.py          # site at http://localhost:8000/
```
PDF reading and live agents need a free local model: `ollama pull llama3.1:8b` (see `demo3/LOCAL_MODEL.md`). No API key is used anywhere in the published results.

All contracts, change proposals and sample PDFs are synthetic, written by the team with AI assistance and modeled on public audit findings.
