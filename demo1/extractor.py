#!/usr/bin/env python3
"""Demo 1: contract rules extractor.

Reads a contract (markdown or plain text), splits it into sections, asks Claude to
extract each explicit rule as structured data, verifies that every quoted phrase
really appears in the contract, and writes the result to JSON.

Usage:
    export ANTHROPIC_API_KEY=...
    python extractor.py                       # uses data/synthetic_contract.md
    python extractor.py --dry-run             # show the chunks and prompt sizes, no API calls
    python extractor.py --model claude-sonnet-5-5 --out results/extracted_rules.json

The answer key is NOT read by this script, and must not be used to tune the prompts
after you have seen results. See README.md.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from common import RULE_TYPES, UNITS, normalize

ROOT = Path(__file__).resolve().parent
DEFAULT_CONTRACT = ROOT / "data" / "synthetic_contract.md"
DEFAULT_OUT = ROOT / "results" / "extracted_rules.json"
CACHE_DIR = ROOT / "results" / "cache"
SYSTEM_PROMPT_FILE = ROOT / "prompts" / "extract_system.txt"
USER_PROMPT_FILE = ROOT / "prompts" / "extract_user.txt"
DEFAULT_MODEL = os.environ.get("EXTRACTOR_MODEL", "claude-sonnet-5-5")

TOOL = {
    "name": "record_rules",
    "description": "Record every explicit rule found in the contract text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "rules": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": RULE_TYPES},
                        "sections": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Section numbers as written, e.g. '6.2(a)' or 'Exhibit E 01 26 00'.",
                        },
                        "summary": {"type": "string", "description": "One plain-English sentence stating the rule."},
                        "value": {
                            "type": ["object", "null"],
                            "properties": {
                                "number": {"type": "number"},
                                "unit": {"type": "string", "enum": UNITS},
                            },
                            "required": ["number", "unit"],
                            "description": "The key number and its unit, or null if the rule has no number.",
                        },
                        "trigger": {
                            "type": ["string", "null"],
                            "description": "For time periods: the event the period starts from, in the contract's words.",
                        },
                        "applies_to": {"type": ["string", "null"], "description": "The party the rule applies to."},
                        "exceptions": {"type": ["string", "null"], "description": "Any exception stated for this rule."},
                        "quote": {
                            "type": "string",
                            "description": "Exact contiguous phrase (5 to 30 words) copied from the text.",
                        },
                    },
                    "required": ["type", "sections", "summary", "value", "quote"],
                },
            }
        },
        "required": ["rules"],
    },
}


# --------------------------------------------------------------------------- chunking
def split_into_sections(text: str):
    """Split on level-2 markdown headings (Articles and Exhibits). Front matter is skipped."""
    parts = re.split(r"(?m)^## ", text)
    sections = []
    for part in parts[1:]:
        title, _, body = part.partition("\n")
        sections.append((title.strip(), body.strip()))
    return sections


def group_sections(sections, max_chars=4500):
    """Merge neighboring small sections so each API call has a reasonable amount of text."""
    groups, current, size = [], [], 0
    for title, body in sections:
        block = f"## {title}\n{body}"
        if current and size + len(block) > max_chars:
            groups.append(current)
            current, size = [], 0
        current.append((title, block))
        size += len(block)
    if current:
        groups.append(current)
    return [
        {"titles": [t for t, _ in g], "text": "\n\n".join(b for _, b in g)}
        for g in groups
    ]


def get_definitions(sections):
    for title, body in sections:
        if title.lower().startswith("article 1."):
            return f"## {title}\n{body}"
    return "(none)"


# --------------------------------------------------------------------------- model call
def build_user_prompt(template: str, definitions: str, section_text: str) -> str:
    return template.replace("[[DEFINITIONS]]", definitions).replace("[[SECTION_TEXT]]", section_text)


def cache_key(model, system, user):
    return hashlib.sha256(f"{model}\n{system}\n{user}".encode("utf-8")).hexdigest()[:24]


def call_model(client, model, system, user, max_tokens=8000, retries=3):
    """Call Claude with a forced tool call and return (rules, usage dict)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{cache_key(model, system, user)}.json"
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        return cached["rules"], cached["usage"], True

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0,
                system=system,
                tools=[TOOL],
                tool_choice={"type": "tool", "name": TOOL["name"]},
                messages=[{"role": "user", "content": user}],
            )
            rules = []
            for block in response.content:
                if getattr(block, "type", None) == "tool_use" and block.name == TOOL["name"]:
                    rules = block.input.get("rules", [])
            usage = {
                "input_tokens": getattr(response.usage, "input_tokens", 0),
                "output_tokens": getattr(response.usage, "output_tokens", 0),
            }
            path.write_text(json.dumps({"rules": rules, "usage": usage}, indent=2), encoding="utf-8")
            return rules, usage, False
        except Exception as exc:  # network errors, rate limits, malformed output
            last_error = exc
            wait = 2 ** attempt
            print(f"  attempt {attempt} failed ({type(exc).__name__}: {exc}); retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"Model call failed after {retries} attempts: {last_error}")


# --------------------------------------------------------------------------- post-processing
def verify_quotes(rules, contract_text):
    """Mark each rule with whether its quote appears verbatim in the contract text."""
    norm_contract = normalize(contract_text)
    for rule in rules:
        quote = normalize(rule.get("quote", ""))
        rule["quote_verified"] = bool(quote) and quote in norm_contract
    return rules


def clean_and_dedupe(rules):
    seen, out = set(), []
    for rule in rules:
        rule.setdefault("value", None)
        rule.setdefault("sections", [])
        key = (normalize(rule.get("quote", "")).lower(), rule.get("type"), json.dumps(rule.get("value"), sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        out.append(rule)
    for i, rule in enumerate(out, start=1):
        rule["id"] = f"E{i:03d}"
    return out


# --------------------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description="Extract contract rules with Claude.")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-chars", type=int, default=4500, help="approximate characters of contract text per call")
    parser.add_argument("--dry-run", action="store_true", help="show chunks and prompt sizes without calling the API")
    args = parser.parse_args()

    contract_text = Path(args.contract).read_text(encoding="utf-8")
    system = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
    template = USER_PROMPT_FILE.read_text(encoding="utf-8").strip()

    sections = split_into_sections(contract_text)
    definitions = get_definitions(sections)
    groups = group_sections(sections, args.max_chars)

    print(f"Contract: {args.contract}")
    print(f"Sections: {len(sections)} -> {len(groups)} API calls (model: {args.model})")

    if args.dry_run:
        for i, g in enumerate(groups, start=1):
            user = build_user_prompt(template, definitions, g["text"])
            print(f"  call {i}: {len(user):>6} chars | {', '.join(g['titles'])}")
        print("Dry run only. No API calls made.")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Export it, or use --dry-run.")
    try:
        import anthropic
    except ImportError:
        sys.exit("The 'anthropic' package is not installed. Run: pip install -r requirements.txt")

    client = anthropic.Anthropic()
    all_rules, total_in, total_out, cached_calls = [], 0, 0, 0

    for i, g in enumerate(groups, start=1):
        # Each call sees Article 1 definitions as reference, except when Article 1 is the section itself.
        defs = "(see section below)" if any(t.lower().startswith("article 1.") for t in g["titles"]) else definitions
        user = build_user_prompt(template, defs, g["text"])
        print(f"[{i}/{len(groups)}] {', '.join(g['titles'])}")
        rules, usage, was_cached = call_model(client, args.model, system, user)
        cached_calls += int(was_cached)
        total_in += usage["input_tokens"]
        total_out += usage["output_tokens"]
        for rule in rules:
            rule["source_chunk"] = i
        all_rules.extend(rules)
        print(f"    {len(rules)} rules{' (cached)' if was_cached else ''}")

    all_rules = verify_quotes(all_rules, contract_text)
    all_rules = clean_and_dedupe(all_rules)

    verified = sum(1 for r in all_rules if r["quote_verified"])
    result = {
        "meta": {
            "contract_file": os.path.basename(args.contract),
            "model": args.model,
            "created": datetime.now(timezone.utc).isoformat(),
            "calls": len(groups),
            "cached_calls": cached_calls,
            "input_tokens": total_in,
            "output_tokens": total_out,
            "system_prompt_sha256": hashlib.sha256(system.encode()).hexdigest()[:16],
            "user_prompt_sha256": hashlib.sha256(template.encode()).hexdigest()[:16],
            "total_rules": len(all_rules),
            "quotes_verified": verified,
        },
        "rules": all_rules,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nExtracted {len(all_rules)} rules; {verified} have verbatim quotes. Saved to {out_path}")
    print("Next: python evaluate.py")


if __name__ == "__main__":
    main()
