# ClauseStream · INFO 492 C, Team 6

Yousuf Shaik, Sriharshith Paruchuri, Nithika Yechuri · University of Washington Information School, Autumn 2026

**Thesis.** An agent that checks each construction handoff (RFI answer → change notice → priced proposal → change order) against the contract can catch rule violations when the paperwork is submitted, instead of in a post-payment audit. People make every decision. Project lens: the Webster School audit (Seattle Public Schools, 2023).

**Site:** https://info492-team6.vercel.app/

| Page | What |
|---|---|
| [`/`](https://info492-team6.vercel.app/) | Landing page. The only page that links to the research |
| [`/app/`](https://info492-team6.vercel.app/app/) | **The product**: one platform for every party, sub to owner. Home, change threads (sub request → GC/CM proposal → architect → owner), record, contracts, schedule and delay, activity log, project settings, plus one quick check. Opens on its own. New visitors land on a getting-started screen (`/app/#start`): try the sample as a sub, GC/CM, architect or owner's rep with a step-by-step guide, or start a real project with a set-up checklist. `/app/?project=sample` opens the sample directly (synthetic, runs in the browser, nothing saved) with a *Viewing as* picker |
| [`/app/field/`](https://info492-team6.vercel.app/app/field/) | Field link: a no-sign-in page a sub's crew uses to send a note and photos; the sub confirms it before anyone else sees it |
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
| `demo4/` | Schedule and delay data: cases with time, the June 2020 schedule, contract terms answer key |
| `app/`, `assets/` | The product. `platform.js` (sample/live mode, seeding), `views-platform.js` (the screens), `rules.js` (who sees what and what moves a change, the same rules as the database), `demo-db.js` (in-browser stand-in for the database), `checks.js`, `contract.js`, `schedule.js`, `delay.js` (the computed checks), `app.js` (quick check and routing), `views-time.js` (schedule and delay), `guide.js` (sign-in page with role selection and the guide panel; each step ticks off from the project's data, not from clicks), `views-runs.js` (07 Agent runs: the real-data evaluation). `app/samples/` holds synthetic sample PDFs |
| `record/` | The synthetic project record (`bundle.json`, `docs/`) and, in `record/platform/`, the synthetic companies, contracts, schedule of values, schedule versions and sub requests, with an answer key written by a separate helper that never saw the code |
| `data/real/` | Real public construction records (67 PDFs with checksums), the 173 extracted RFIs with official answers, document pieces, and the evaluation results |
| `supabase/` | `migrations/0003_platform.sql` (the whole database, with row-level security) and `tests/` |
| `api/config.js` | Gives the site the public Supabase URL and anon key. The service key is never used in the site |
| `index.html`, `research/`, `thesis/`, `demos/`, `demo1/`–`demo3/`, `log/`, `sources/` | Site pages |
| `tools/` | Tests (below), sample PDF generator |
| `docs/` | Class feedback, Demo 4 spec |
| `.github/workflows/` | Free runs on GitHub's machines: demo runs on local models, the PDF reader test, the record drafter test |

## Demo 4: real industry data
The agentic system is evaluated on **173 real RFIs** from six public construction projects (State of Maine, Illinois Capital Development Board, Roosevelt Island Operating Corporation), each with the official answer the agency published. An RFI responder searches the project's own contract and spec documents, drafts a response and quotes its sources; code scores it against the official answers. Results: the app's **07 Agent runs** tab and `data/real/results/summary.json`. Sources, checksums, extraction and known gaps: [`data/real/README.md`](data/real/README.md). Personas and stakeholder feedback rounds: `/research/personas/` and `/research/feedback/`.

| Step | Command |
|---|---|
| Download the public records | `python3 tools/real/fetch.py` (or Actions → “Fetch public records”) |
| Extract RFIs, answers and document pieces | `python3 tools/real/extract.py` |
| Run a model (Ollama running locally) | `python3 tools/real/rfi_eval.py --model qwen3.5:9b` |
| Score | `python3 tools/real/score.py` |
| All models on GitHub's free machines | Actions → “Real RFI evaluation” |

Dependencies: `requirements.txt` (plus pdftotext, Node.js and Ollama).

## Run it locally
```bash
python3 demo3/serve_local.py          # site at http://localhost:8000/ (live AI if Ollama is running)
```
PDF reading and live AI drafts need a free local model: `ollama pull llama3.1:8b` (see `demo3/LOCAL_MODEL.md`). Online, the site uses saved runs. No API key is used anywhere.

## Tests
```bash
python3 demo3/tests/test_demo3.py     # offline tests
node tools/parity.js                  # browser checks match Python on all 36 test proposals
node tools/contract_parity.js         # contract term reading, 3 contracts
node tools/schedule_test.js           # schedule import and CPM, 143 checks
node tools/delay_test.js              # delay analysis vs answer key, 20 change orders
node tools/tia_crosscheck.js          # time impact analysis cross-check, 57 checks
node tools/rules_test.js              # who sees what, in the browser stand-in, 27 checks
node tools/platform_test.js           # flow-down gaps, cost per day, roll-ups, visibility vs the helper's answer key, 107 checks
bash tools/db_test.sh                 # the same visibility scenario on a real Postgres with the migration
python3 tools/guide_test.py           # all four sample guides end to end, in Chrome (serve the site on :8765 first)
python3 tools/nav_audit.py            # navigation audit: every page and link, every app screen for all four parties, every control (~40 min)
node tools/extract_score.js           # PDF reader on the sample PDFs (needs Ollama)
```

## Database (Supabase)
Run `supabase/migrations/0003_platform.sql` once in the Supabase SQL Editor. It is a fresh start: it drops the tables from earlier versions and creates everything, so it is safe to re-run. Earlier migrations (0001, 0002) are in git history only.

## Not built yet
- Real email and reminders (the app shows in-app alerts today).
- Text-message check on the field link.
- A long-term way to give users AI online. Today: saved runs online (`record/results/draft_llama3.1_8b.json`), live AI on a laptop running Ollama.
- Procore and Newforma connections (stubs only).

All contracts, change proposals and sample PDFs are synthetic, written by the team with AI assistance and modeled on public audit findings.
