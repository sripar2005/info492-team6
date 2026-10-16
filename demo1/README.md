# Demo 1: Contract Rules Extractor (INFO 492 C, Team 6)

This demo tests **claim 1** of our thesis: the pricing and notice rules in a GC/CM contract can be extracted into a checkable, citable form, capturing **at least 85% of the contract's core rules**. It is the foundation for later demos (change classifier, handoff checker, approval-gated thread), which need the rules in structured form before they can check anything.

## What is in this repo

| Path | What it is |
| --- | --- |
| `data/synthetic_contract.md` | The synthetic GC/CM agreement (input to the extractor) |
| `data/answer_key.json` | Hand-checkable key: 132 rules (124 core), each with an exact anchor quote |
| `data/build_answer_key.py` | Builds the key and verifies every anchor appears once in the contract |
| `prompts/extract_system.txt`, `prompts/extract_user.txt` | The LLM prompts, exactly as used |
| `extractor.py` | Splits the contract, calls Claude, verifies quotes, writes JSON |
| `evaluate.py` | Scores the extraction against the key and writes a report |
| `common.py` | Shared helpers (text normalization, rule types) |
| `tests/test_pipeline.py` | Offline tests for chunking and scoring (no API key needed) |
| `results/` | Output of runs: `extracted_rules.json`, `evaluation.json`, `evaluation_report.md` |

## Run it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here

python tests/test_pipeline.py      # offline checks, no API calls
python extractor.py --dry-run      # shows the 6 API calls it will make
python extractor.py                # runs the extractor (about 6 calls)
python evaluate.py                 # scores it, writes results/evaluation_report.md
```

Set another model with `--model` or the `EXTRACTOR_MODEL` environment variable. Responses are cached in `results/cache/`, so re-running the same prompts costs nothing and gives identical output.

## How it works

1. **Split:** the contract is split at each Article and Exhibit heading, and neighboring small sections are grouped (about 4,500 characters per call).
2. **Extract:** each group goes to Claude with the Article 1 definitions as reference. The model is told to answer through the `record_rules` tool, and a response without that tool call is retried rather than counted as zero rules, so the output is structured JSON (type, sections, summary, value and unit, trigger, applies_to, exceptions, quote). The model's default sampling is used (see "Code fixes"); every response is cached, so re-running the evaluation reads the same output.
3. **Verify:** every quote is checked against the contract text after normalization. A rule whose quote is not found is flagged as a possible fabrication.
4. **Score:** a key rule is FOUND when an extracted rule points at the same text (its verified quote overlaps the key's anchor) and carries the same number and unit. Overlap with the wrong value is counted separately as WRONG VALUE.

## Measures and targets (set before running)

| Measure | Definition | Target |
| --- | --- | --- |
| Core recall | key core rules found / core rules | at least 85% (claim 1) |
| Precision | extracted rules supported by the key / extracted rules | report only |
| Citation validity | quotes found verbatim / extracted rules | report only (aim for 100%) |
| Wrong value | right text, wrong number or unit | report only |
| Trap recall | recall on fee exceptions, negative rules, and same-length clocks | report only |

Do not change the targets, the key, or the prompts after seeing results. If you change anything, record it as a new run and say so in the demo note.

## Data justification (synthetic contract)

Real contracts for completed public school projects are not downloadable without a records request, and a request would not return in time. We wrote a synthetic agreement modeled on a publicly documented school GC/CM project (Seattle Public Schools' Webster School). Public inputs: GC/CM delivery, a GMP of $26,240,507, the AIA A133-2009 base form, the Specified General Conditions / Negotiated Support Services / self-performed work categories, a 5% fee, CP numbering, Construction Change Directives, and Board approval of larger change orders (from the project's public audit and board action reports), plus the standard AIA A201-2017 structure and the range of response and notice periods in public owner-modified A201s. Everything else (dollar breakdowns, daily rates, markups, equipment rules, deadlines, the $250,000 approval threshold, dates, party names) is invented. The contract contains deliberate difficulty: rules scattered across Articles, exhibits, and Division 01; similar clocks with different triggers; fee exceptions; negative rules; and a precedence clause. This is a limitation: the results show whether the method works on a contract with these features, not on any real contract.

## Limits

- The answer key was written by us from our own contract. A teammate should review it before results are reported.
- The contract is synthetic, and one contract is one case.
- Matching is by text overlap and value, so it can miss a correct extraction that quotes a different part of the same rule. The report lists misses and unsupported extractions for manual review.
- Extracted rules that the key does not support may be real rules the key missed. Review them before treating them as errors.

## Code fixes

Bug fixes made after the code was written, before any results existed. No prompt, answer key entry, or target was changed.

| Date | Change | Why |
| --- | --- | --- |
| 2026-10-15 | Removed `temperature=0` from the API call in `extractor.py`; pinned `anthropic>=1.15,<2` in `requirements.txt` | The first live run failed before reaching the API: anthropic SDK 1.x no longer accepts a `temperature` argument (`TypeError: Messages.create() got an unexpected keyword argument 'temperature'`). No API call was made and no results were produced. The extractor now uses the model's default sampling, so a fresh run may differ slightly from ours; the cached responses and committed `results/` files are the record of our run. |
| 2026-10-15 | Changed `tool_choice` from forcing `record_rules` to `auto`; added a check that retries, then fails, if the model returns no `record_rules` call | The second live run reached the API, which returned `400 invalid_request_error: tool_choice: type "tool" and "any" are not supported for this model`. No output was produced. The system prompt already instructs the model to call `record_rules` (unchanged), and the tool schema is unchanged. The new check ensures a missing tool call can never be scored as an empty extraction. |
