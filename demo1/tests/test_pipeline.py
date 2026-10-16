"""Offline tests: no API key needed.

Builds a simulated extraction from the answer key with known, deliberate errors and
checks that the evaluator reports exactly the numbers we expect. This tests the
scoring code, not the model.

Run:  python tests/test_pipeline.py
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common import normalize  # noqa: E402
from evaluate import evaluate  # noqa: E402
from extractor import get_definitions, group_sections, split_into_sections, verify_quotes  # noqa: E402

contract_text = (ROOT / "data" / "synthetic_contract.md").read_text(encoding="utf-8")
key = json.loads((ROOT / "data" / "answer_key.json").read_text(encoding="utf-8"))


def test_chunking():
    sections = split_into_sections(contract_text)
    titles = [t for t, _ in sections]
    assert len(sections) == 19, len(sections)  # Articles 1-14 and Exhibits A-E
    assert titles[0].startswith("Article 1.") and titles[-1].startswith("Exhibit E.")
    assert "Change Order (CO)" in get_definitions(sections)
    groups = group_sections(sections, 4500)
    assert 4 <= len(groups) <= 12, len(groups)
    covered = "".join(g["text"] for g in groups)
    assert "6.5.3 CM" in covered and "Section 01 33 00" in covered
    print(f"chunking ok: {len(sections)} sections -> {len(groups)} calls")


def perfect_extraction():
    rules = []
    for i, k in enumerate(key["rules"], start=1):
        rules.append({
            "id": f"E{i:03d}", "type": k["type"], "sections": list(k["sections"]),
            "summary": k["summary"], "value": copy.deepcopy(k["value"]), "quote": k["anchor"],
        })
    return rules


def test_perfect_extraction_scores_100():
    rules = verify_quotes(perfect_extraction(), contract_text)
    result = evaluate(copy.deepcopy(key), {"rules": rules}, contract_text)
    m = result["metrics"]
    assert m["recall_core"] == 1.0 and m["recall_all"] == 1.0, m
    assert m["citation_validity"] == 1.0 and m["wrong_value_count"] == 0
    assert m["meets_target"] is True
    print("perfect extraction scores 100%: ok")


def test_known_errors_are_counted():
    key_rules = key["rules"]
    rules = perfect_extraction()

    # 1) drop 10 rules, 2) corrupt 6 values, 3) fabricate 4 quotes, 4) add 5 extra rules
    drop_idx = set(range(3, 133, 13))  # 10 rules
    drop_idx = {i for i in drop_idx if i < len(rules)}
    value_idx = [i for i in range(len(rules)) if rules[i]["value"] is not None and i not in drop_idx][:6]
    fake_idx = [i for i in range(len(rules)) if i not in drop_idx and i not in value_idx and rules[i]["value"] is None][:4]

    for i in value_idx:
        rules[i]["value"]["number"] += 1
    for i in fake_idx:
        rules[i]["quote"] = "this sentence does not appear anywhere in the contract"
    extras = [
        "Example School District No. 1",
        "School Modernization and Addition",
        "Example Architecture, PLLC",
        "Effective Date: June 17, 2019",
        "Guaranteed Maximum Price: $26,240,507",
    ]
    kept = [r for i, r in enumerate(rules) if i not in drop_idx]
    for j, q in enumerate(extras):
        kept.append({"id": f"X{j}", "type": "process", "sections": ["front matter"], "summary": "extra", "value": None, "quote": q})
    for n, r in enumerate(kept, start=1):
        r["id"] = f"E{n:03d}"
    kept = verify_quotes(kept, contract_text)

    dropped_ids = {key_rules[i]["id"] for i in drop_idx}
    result = evaluate(copy.deepcopy(key), {"rules": kept}, contract_text)
    m = result["metrics"]

    expected_found = len(key_rules) - len(drop_idx) - len(value_idx)
    assert m["found_all"] == expected_found, (m["found_all"], expected_found)
    assert m["wrong_value_count"] == len(value_idx), m["wrong_value_count"]
    assert m["missed_count"] == len(drop_idx), m["missed_count"]
    assert {r["id"] for r in result["missed"]} == dropped_ids
    assert round(m["citation_validity"] * len(kept)) == len(kept) - len(fake_idx)
    # The extras overlap no answer-key anchor, so they must be reported as possible false positives.
    assert len(result["possible_false_positives"]) >= len(extras)
    print(f"known errors counted correctly: found {m['found_all']}, wrong value {m['wrong_value_count']}, "
          f"missed {m['missed_count']}, unverified quotes {len(fake_idx)}")


def test_normalization_survives_formatting_differences():
    pdf_style = "No Fee is added to  NSS,\nand NSS changes only by CO."
    assert normalize("**No Fee is added to NSS, and NSS changes only by CO.**") == normalize(pdf_style)
    assert normalize("CM\u2019s Fee") == normalize("CM's Fee")
    print("normalization ok")


if __name__ == "__main__":
    test_chunking()
    test_perfect_extraction_scores_100()
    test_known_errors_are_counted()
    test_normalization_survives_formatting_differences()
    print("\nAll offline tests passed.")
