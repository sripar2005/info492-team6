# Real industry data: public construction records

Demo 4 is evaluated on **real** RFIs from public construction projects, not on synthetic data.

## Where it comes from

Public agencies publish their bid-phase RFI logs, with the official answers, as addenda to the bid documents, along with the contract and specification text. Our owner’s-rep stakeholder pointed us to public records as the route to real data (public contracting documents are open to disclosure). Team 6 compiled the list of projects and documents in [`Public_Construction_RFI_Logs_and_Contract_Documents.pdf`](Public_Construction_RFI_Logs_and_Contract_Documents.pdf).

| File | What |
|---|---|
| `sources.json` | Every document link from that list (67 PDFs, 24 projects) |
| `pdf/<project>/` | The downloaded PDFs, unchanged |
| `manifest.json` | For each PDF: source link, download time, size and SHA-256, so anyone can confirm it is the same public file |
| `rfis.json` | 173 RFIs with their official published answers, from the 6 projects below |
| `docs/<project>.json` | Each project’s contract and specification text, split into citable pieces (document, section, text) |
| `results/<model>/<project>.json` | Each model’s answers, with what it was shown and how long it took |
| `results/summary.json` | The scores |

## The six projects in the evaluation

Chosen because each publishes **both** an RFI log with official answers **and** the contract or specification text those answers rely on.

| Project | Agency | RFIs | Documents searched |
|---|---|---|---|
| Capitol Parking Garage 2026 Repairs (BGS #2995) | State of Maine, Bureau of General Services | 19 of 21 | Addendum 1 with the 00 72 13 General Conditions |
| Drug Discovery and Cancer Research Pavilion, UIC (CDB #830-030-167), design-build | Illinois Capital Development Board | 30 | Request for Proposals; design-build supplement |
| Northern Illinois Center for Community Sustainability (CDB #822-010-135), design-build | Illinois Capital Development Board | 28 | Request for Proposal; design-build supplement |
| IDOT Materials Lab (CDB #630-442-057), design-build | Illinois Capital Development Board | 8 | Request for Proposal |
| Wellness Center Re-Use Renovation (BGS #3843) | State of Maine, Bureau of General Services | 41 | Project Manual (contract, definitions, general conditions); Addendum 1 |
| Eleanor’s Pier Repair (RFP #26-1095) | Roosevelt Island Operating Corporation | 47 | RFP; RIOC Standard Form Contract for Construction |

## How the RFIs are extracted

`tools/real/extract.py`, no hand edits. The logs come in three layouts, as they would in practice:
- numbered questions followed by “A.” or “Response –” answers (Maine #2995, the Illinois projects),
- “Q.” / “A.” pairs (IDOT),
- ruled tables, read cell by cell from the PDF (Maine #3843 with the answering discipline, Eleanor’s Pier).

Known gaps: 2 of the 21 garage RFIs don’t parse; the Illinois projects published more RFI files than the three used for each; and most bid-phase RFIs refer to drawings, which aren’t in the public text, so few name a spec section that can be checked.

## Reproduce

```bash
python3 tools/real/fetch.py       # download (or use the committed PDFs)
python3 tools/real/extract.py     # RFIs and document pieces
python3 tools/real/rfi_eval.py --model qwen3.5:9b    # needs Ollama running locally
python3 tools/real/score.py       # the scores
```
Or on GitHub: Actions → “Fetch public records”, then “Real RFI evaluation”. Free: open models through Ollama, no API key.
