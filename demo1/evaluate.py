#!/usr/bin/env python3
"""Score extracted rules against the answer key (thesis claim 1).

A key rule counts as FOUND when at least one extracted rule
  1. points at the same text (its verified quote overlaps the key's anchor phrase;
     if the quote could not be verified, the cited section must match instead), and
  2. carries the same value (number and unit), when the key rule has a value.

Overlap with the wrong value is reported separately as WRONG VALUE.

Usage:
    python evaluate.py
    python evaluate.py --extracted results/extracted_rules.json --target 0.85
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from common import normalize, normalize_section, normalize_unit

ROOT = Path(__file__).resolve().parent


def find_span(norm_text, phrase):
    phrase = normalize(phrase)
    if not phrase:
        return None
    idx = norm_text.find(phrase)
    return None if idx < 0 else (idx, idx + len(phrase))


def spans_overlap(a, b):
    return a is not None and b is not None and a[0] < b[1] and b[0] < a[1]


def sections_match(pred_sections, key_sections):
    for p in pred_sections or []:
        for k in key_sections or []:
            p_n, k_n = normalize_section(p), normalize_section(k)
            if p_n and k_n and (p_n == k_n or p_n.startswith(k_n) or k_n.startswith(p_n)):
                return True
    return False


def value_equal(pred_value, key_value):
    if key_value is None:
        return True
    if not pred_value:
        return False
    try:
        same_number = abs(float(pred_value["number"]) - float(key_value["number"])) < 1e-9
    except (KeyError, TypeError, ValueError):
        return False
    return same_number and normalize_unit(pred_value.get("unit")) == normalize_unit(key_value.get("unit"))


def evaluate(key, extraction, contract_text, target=0.85):
    norm_contract = normalize(contract_text)
    key_rules = key["rules"]
    preds = extraction["rules"]

    for p in preds:
        # Verify here so the score never depends on a flag written by the extractor.
        p["_span"] = find_span(norm_contract, p.get("quote", ""))
        p["_verified"] = p["_span"] is not None
    for k in key_rules:
        k["_span"] = find_span(norm_contract, k["anchor"])

    found, wrong_value, missed = {}, {}, []
    supported = set()
    type_agree = 0

    for k in key_rules:
        candidates = []
        for p in preds:
            if spans_overlap(p["_span"], k["_span"]):
                candidates.append(p)
            elif not p["_verified"] and sections_match(p.get("sections"), k["sections"]):
                candidates.append(p)  # fallback for quotes that could not be verified
        good = [p for p in candidates if value_equal(p.get("value"), k["value"])]
        if good:
            best = next((p for p in good if p.get("type") == k["type"]), good[0])
            found[k["id"]] = best["id"]
            type_agree += int(best.get("type") == k["type"])
            supported.update(p["id"] for p in good)
        elif candidates:
            wrong_value[k["id"]] = [
                {"extracted_id": p["id"], "extracted_value": p.get("value"), "key_value": k["value"]}
                for p in candidates
            ]
        else:
            missed.append(k["id"])

    key_by_id = {k["id"]: k for k in key_rules}
    core_ids = [k["id"] for k in key_rules if k["core"]]
    found_core = [i for i in core_ids if i in found]

    false_positives = [p for p in preds if p["id"] not in supported]
    verified_count = sum(1 for p in preds if p["_verified"])

    # recall by type
    by_type = defaultdict(lambda: [0, 0])
    for k in key_rules:
        by_type[k["type"]][1] += 1
        by_type[k["type"]][0] += int(k["id"] in found)

    def group_recall(ids):
        ids = [i for i in ids if i in key_by_id]
        return (sum(1 for i in ids if i in found) / len(ids)) if ids else None

    trap_groups = {
        "fee_exclusions (pitfall P3)": [k["id"] for k in key_rules if k["type"] == "fee_exclusion"],
        "negative_rules (pitfall P4)": [k["id"] for k in key_rules if k["type"] == "non_authorization"],
        "confusable_clocks (pitfall P1)": sorted({i for ids in key.get("confusable_clocks", {}).values() for i in ids}),
    }

    n_key, n_pred = len(key_rules), len(preds)
    metrics = {
        "key_rules": n_key,
        "core_rules": len(core_ids),
        "extracted_rules": n_pred,
        "found_all": len(found),
        "found_core": len(found_core),
        "recall_all": len(found) / n_key if n_key else 0,
        "recall_core": len(found_core) / len(core_ids) if core_ids else 0,
        "precision": len(supported) / n_pred if n_pred else 0,
        "citation_validity": verified_count / n_pred if n_pred else 0,
        "wrong_value_count": len(wrong_value),
        "missed_count": len(missed),
        "type_label_agreement": type_agree / len(found) if found else 0,
        "target_recall_core": target,
        "meets_target": (len(found_core) / len(core_ids) if core_ids else 0) >= target,
        "recall_by_type": {t: {"found": f, "total": n, "recall": f / n} for t, (f, n) in sorted(by_type.items())},
        "recall_trap_groups": {name: group_recall(ids) for name, ids in trap_groups.items()},
    }

    return {
        "metrics": metrics,
        "missed": [{"id": i, "type": key_by_id[i]["type"], "core": key_by_id[i]["core"],
                    "sections": key_by_id[i]["sections"], "summary": key_by_id[i]["summary"]} for i in missed],
        "wrong_value": [{"id": i, "summary": key_by_id[i]["summary"], "details": d} for i, d in wrong_value.items()],
        "unverified_quotes": [{"id": p["id"], "quote": p.get("quote"), "summary": p.get("summary")}
                              for p in preds if not p["_verified"]],
        "possible_false_positives": [{"id": p["id"], "type": p.get("type"), "sections": p.get("sections"),
                                      "summary": p.get("summary"), "quote": p.get("quote")} for p in false_positives],
        "found_map": found,
    }


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def write_report(result, path, model):
    m = result["metrics"]
    lines = [
        "# Rules extractor evaluation",
        "",
        f"Model: `{model}`",
        "",
        f"**Claim 1 target:** at least {pct(m['target_recall_core'])} of core rules captured. "
        f"**Result: {pct(m['recall_core'])} ({m['found_core']} of {m['core_rules']}). "
        f"{'Target met.' if m['meets_target'] else 'Target not met.'}**",
        "",
        "| Measure | Result |",
        "| --- | --- |",
        f"| Recall, core rules | {pct(m['recall_core'])} ({m['found_core']}/{m['core_rules']}) |",
        f"| Recall, all rules | {pct(m['recall_all'])} ({m['found_all']}/{m['key_rules']}) |",
        f"| Precision (extracted rules supported by the key) | {pct(m['precision'])} |",
        f"| Citation validity (quotes found verbatim) | {pct(m['citation_validity'])} |",
        f"| Right text, wrong value | {m['wrong_value_count']} |",
        f"| Type label agreement among found rules | {pct(m['type_label_agreement'])} |",
        f"| Rules extracted | {m['extracted_rules']} |",
        "",
        "## Recall on the contract's built-in traps",
        "",
        "| Pitfall | Recall |",
        "| --- | --- |",
    ]
    for name, r in m["recall_trap_groups"].items():
        lines.append(f"| {name} | {pct(r)} |")

    lines += ["", "## Recall by rule type", "", "| Type | Found | Total | Recall |", "| --- | --- | --- | --- |"]
    for t, d in m["recall_by_type"].items():
        lines.append(f"| {t} | {d['found']} | {d['total']} | {pct(d['recall'])} |")

    def section(title, items, fmt):
        lines.extend(["", f"## {title} ({len(items)})", ""])
        lines.extend([fmt(i) for i in items] or ["None."])

    section("Missed rules", result["missed"],
            lambda r: f"- {r['id']} ({r['type']}, {'core' if r['core'] else 'peripheral'}, {', '.join(r['sections'])}): {r['summary']}")
    section("Right text, wrong value", result["wrong_value"],
            lambda r: f"- {r['id']}: {r['summary']} | extracted value(s): "
                      + "; ".join(str(d['extracted_value']) for d in r['details']) + f" | key value: {r['details'][0]['key_value']}")
    section("Quotes not found in the contract", result["unverified_quotes"],
            lambda r: f"- {r['id']}: \"{r['quote']}\"")
    section("Extracted rules not supported by the key (review: could be real rules the key missed, or errors)",
            result["possible_false_positives"],
            lambda r: f"- {r['id']} ({r['type']}, {', '.join(r['sections'] or [])}): {r['summary']}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Score extracted rules against the answer key.")
    parser.add_argument("--key", default=str(ROOT / "data" / "answer_key.json"))
    parser.add_argument("--extracted", default=str(ROOT / "results" / "extracted_rules.json"))
    parser.add_argument("--contract", default=str(ROOT / "data" / "synthetic_contract.md"))
    parser.add_argument("--out", default=str(ROOT / "results"))
    parser.add_argument("--target", type=float, default=0.85, help="claim 1 recall target for core rules")
    args = parser.parse_args()

    key = json.loads(Path(args.key).read_text(encoding="utf-8"))
    extraction = json.loads(Path(args.extracted).read_text(encoding="utf-8"))
    contract_text = Path(args.contract).read_text(encoding="utf-8")

    result = evaluate(key, extraction, contract_text, args.target)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "evaluation.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    write_report(result, out_dir / "evaluation_report.md", extraction.get("meta", {}).get("model", "unknown"))

    m = result["metrics"]
    print(f"Core recall:        {pct(m['recall_core'])} ({m['found_core']}/{m['core_rules']})  target {pct(m['target_recall_core'])}  -> {'MET' if m['meets_target'] else 'NOT MET'}")
    print(f"All-rule recall:    {pct(m['recall_all'])}")
    print(f"Precision:          {pct(m['precision'])}")
    print(f"Citation validity:  {pct(m['citation_validity'])}")
    print(f"Wrong value:        {m['wrong_value_count']}   Missed: {m['missed_count']}")
    print(f"Report: {out_dir / 'evaluation_report.md'}")


if __name__ == "__main__":
    main()
