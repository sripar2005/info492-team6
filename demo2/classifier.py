#!/usr/bin/env python3
"""Demo 2: change classifier.

For each incoming document in data/cases.json, asks Claude (with the full contract as context)
whether it is a CLARIFICATION or a POSSIBLE CHANGE, which Section 6.2 notice rule applies, the
notice due date, the deciding sections, and a supporting quote. Then:
  - checks the quote really appears in the contract, and
  - computes the notice due date in code from the model's chosen rule (deadlines.py),
so the deadline can be compared both ways: the model's own date and the code-computed date.

The answer key (data/answer_key.json) is NOT read here.

Usage:
    export ANTHROPIC_API_KEY=...
    python classifier.py --dry-run
    python classifier.py
"""
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "demo1"))
from common import normalize  # noqa: E402  (same text normalization as Demo 1)
from deadlines import NOTICE_RULES, notice_due  # noqa: E402

CONTRACT = ROOT.parent / "demo1" / "data" / "synthetic_contract.md"
# Test sets: A = 30 documents written with the contract; B = 30 written independently by Yousuf Shaik.
SETS = {
    "A": {"cases": ROOT / "data" / "cases.json", "out": ROOT / "results" / "classifications.json", "calendar": "wa2020"},
    "B": {"cases": ROOT / "data" / "set_b" / "cases.json", "out": ROOT / "results" / "set_b" / "classifications.json", "calendar": "us_federal"},
}
CACHE_DIR = ROOT / "results" / "cache"
SYSTEM_PROMPT_FILE = ROOT / "prompts" / "classify_system.txt"
USER_PROMPT_FILE = ROOT / "prompts" / "classify_user.txt"
DEFAULT_MODEL = os.environ.get("CLASSIFIER_MODEL", "claude-sonnet-5-5")

TOOL = {
    "name": "record_classification",
    "description": "Record the classification of one incoming document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "label": {"type": "string", "enum": ["CLARIFICATION", "POSSIBLE CHANGE"]},
            "notice_rule": {"type": "string", "enum": NOTICE_RULES},
            "notice_due": {"type": ["string", "null"], "description": "YYYY-MM-DD, or null for a clarification."},
            "sections": {"type": "array", "items": {"type": "string"}, "description": "Contract sections that decide the answer, e.g. '6.8'."},
            "quote": {"type": "string", "description": "Exact contiguous phrase (5 to 30 words) copied from the contract."},
            "reasoning": {"type": "string", "description": "One or two plain sentences."},
        },
        "required": ["label", "notice_rule", "notice_due", "sections", "quote", "reasoning"],
    },
}


def build_user_prompt(template, contract, case):
    return (template.replace("[[CONTRACT]]", contract).replace("[[SOURCE]]", case["source"])
            .replace("[[FROM]]", case["from"]).replace("[[EVENT_DATE]]", case["event_date"])
            .replace("[[TEXT]]", case["text"]))


def cache_key(model, system, user):
    return hashlib.sha256(f"{model}\n{system}\n{user}".encode("utf-8")).hexdigest()[:24]


def call_model(client, model, system, user, max_tokens=1500, retries=3):
    """Return (answer dict, usage dict, latency seconds, was_cached)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{cache_key(model, system, user)}.json"
    if path.exists():
        c = json.loads(path.read_text(encoding="utf-8"))
        return c["answer"], c["usage"], c["latency_s"], True
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            t0 = time.time()
            response = client.messages.create(
                model=model, max_tokens=max_tokens, system=system, tools=[TOOL],
                tool_choice={"type": "auto"},  # forced tool choice is not supported for this model (see Demo 1 README)
                messages=[{"role": "user", "content": user}],
            )
            latency = round(time.time() - t0, 2)
            calls = [b for b in response.content if getattr(b, "type", None) == "tool_use" and b.name == TOOL["name"]]
            if not calls:
                raise ValueError(f"model did not call {TOOL['name']} (stop_reason={response.stop_reason})")
            answer = dict(calls[0].input)
            usage = {"input_tokens": getattr(response.usage, "input_tokens", 0),
                     "output_tokens": getattr(response.usage, "output_tokens", 0)}
            path.write_text(json.dumps({"answer": answer, "usage": usage, "latency_s": latency}, indent=2), encoding="utf-8")
            return answer, usage, latency, False
        except Exception as exc:
            last_error = exc
            wait = 2 ** attempt
            print(f"  attempt {attempt} failed ({type(exc).__name__}: {exc}); retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"Model call failed after {retries} attempts: {last_error}")


def main():
    parser = argparse.ArgumentParser(description="Classify incoming documents as clarification or possible change.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--set", default="A", choices=sorted(SETS), help="test set: A (default) or B")
    parser.add_argument("--out", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    contract = CONTRACT.read_text(encoding="utf-8")
    cfg = SETS[args.set]
    args.out = args.out or str(cfg["out"])
    cases = json.loads(cfg["cases"].read_text(encoding="utf-8"))["cases"]
    system = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
    template = USER_PROMPT_FILE.read_text(encoding="utf-8").strip()
    print(f"Set {args.set}: {len(cases)} documents, 1 API call each (model: {args.model})")

    if args.dry_run:
        first = build_user_prompt(template, contract, cases[0])
        print(f"  prompt size per call: about {len(system) + len(first):,} characters (contract is {len(contract):,})")
        print("Dry run only. No API calls made.")
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Export it, or use --dry-run.")
    import anthropic
    client = anthropic.Anthropic()

    norm_contract = normalize(contract)
    results, tin, tout, cached = [], 0, 0, 0
    for i, case in enumerate(cases, start=1):
        answer, usage, latency, was_cached = call_model(client, args.model, system, build_user_prompt(template, contract, case))
        tin += usage["input_tokens"]; tout += usage["output_tokens"]; cached += int(was_cached)
        rule = answer.get("notice_rule", "none")
        quote = normalize(answer.get("quote", ""))
        results.append({
            "id": case["id"],
            "answer": answer,
            "quote_verified": bool(quote) and quote in norm_contract,
            "computed_notice_due": notice_due(case["event_date"], rule, cfg["calendar"]) if answer.get("label") == "POSSIBLE CHANGE" else None,
            "latency_s": latency,
            "usage": usage,
        })
        print(f"[{i:>2}/{len(cases)}] {case['id']}: {answer.get('label')} {rule}{' (cached)' if was_cached else ''}")

    out = {
        "meta": {
            "model": args.model,
            "test_set": args.set,
            "created": datetime.now(timezone.utc).isoformat(),
            "calls": len(cases), "cached_calls": cached,
            "input_tokens": tin, "output_tokens": tout,
            "system_prompt_sha256": hashlib.sha256(system.encode()).hexdigest()[:16],
            "user_prompt_sha256": hashlib.sha256(template.encode()).hexdigest()[:16],
        },
        "results": results,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(results)} classifications to {args.out}. Next: python evaluate.py")


if __name__ == "__main__":
    main()
