#!/usr/bin/env python3
"""Score Demo 2's classifications against the answer key.

Measures (target set before the run: label accuracy >= 85%, thesis claim 4):
  - label accuracy: CLARIFICATION vs POSSIBLE CHANGE
  - change recall: of the real changes, how many were flagged (a missed change can forfeit payment)
  - change precision: of the flags, how many were real changes (false alarms cost review time)
  - notice rule accuracy: on real changes the model flagged, did it pick the right 6.2 rule
  - deadline accuracy, two ways: the model's own date vs. the date computed in code from its rule
  - citation validity: the quote appears word for word in the contract
  - accuracy on the 11 tricky cases

Writes results/evaluation.json (with a per-case trace for the website) and results/evaluation_report.md.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHANGE = "POSSIBLE CHANGE"


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def ratio(n, d):
    return n / d if d else None


def evaluate(cases, key, run, target=0.85):
    key_by = {k["id"]: k for k in key}
    case_by = {c["id"]: c for c in cases}
    trace, n = [], 0
    tp = fp = fn = tn = 0
    rule_ok = rule_n = 0
    own_ok = code_ok = due_n = 0
    cite_ok = 0
    tricky_ok = tricky_n = 0
    for r in run["results"]:
        k, a = key_by[r["id"]], r["answer"]
        n += 1
        truth, pred = k["label"], a.get("label")
        label_ok = truth == pred
        if truth == CHANGE and pred == CHANGE: tp += 1
        elif truth != CHANGE and pred == CHANGE: fp += 1
        elif truth == CHANGE and pred != CHANGE: fn += 1
        else: tn += 1
        rule_match = own_match = code_match = None
        if truth == CHANGE and pred == CHANGE:
            rule_n += 1; due_n += 1
            rule_match = a.get("notice_rule") == k["notice_rule"]; rule_ok += rule_match
            own_match = a.get("notice_due") == k["notice_due"]; own_ok += own_match
            code_match = r.get("computed_notice_due") == k["notice_due"]; code_ok += code_match
        cite_ok += bool(r.get("quote_verified"))
        if k["tricky"]:
            tricky_n += 1; tricky_ok += label_ok
        if not label_ok:
            outcome = "missed change" if truth == CHANGE else "false alarm"
        elif truth == CHANGE and not (rule_match and code_match):
            outcome = "right label, wrong deadline"
        else:
            outcome = "correct"
        trace.append({
            "id": r["id"], "case": case_by[r["id"]], "expected": k, "model": a,
            "quote_verified": r.get("quote_verified"), "computed_notice_due": r.get("computed_notice_due"),
            "label_ok": label_ok, "rule_ok": rule_match, "model_date_ok": own_match, "code_date_ok": code_match,
            "outcome": outcome, "latency_s": r.get("latency_s"), "usage": r.get("usage"),
        })
    acc = (tp + tn) / n if n else 0
    metrics = {
        "documents": n,
        "label_accuracy": acc, "target_label_accuracy": target, "meets_target": acc >= target,
        "confusion": {"true_change_flagged": tp, "false_alarm": fp, "missed_change": fn, "true_clarification": tn},
        "change_recall": ratio(tp, tp + fn), "change_precision": ratio(tp, tp + fp),
        "notice_rule_accuracy": ratio(rule_ok, rule_n), "rule_scored_on": rule_n,
        "deadline_accuracy_model_date": ratio(own_ok, due_n), "deadline_accuracy_code_date": ratio(code_ok, due_n), "deadline_scored_on": due_n,
        "citation_validity": ratio(cite_ok, n),
        "tricky_accuracy": ratio(tricky_ok, tricky_n), "tricky_cases": tricky_n,
    }
    return {"metrics": metrics, "trace": trace}


def write_report(result, meta, path):
    m = result["metrics"]; c = m["confusion"]
    lines = [
        f"# Change classifier evaluation (Demo 2, Set {meta.get('test_set', 'A')})", "",
        f"Model: `{meta.get('model')}` · {m['documents']} documents · {meta.get('input_tokens', 0):,} input / {meta.get('output_tokens', 0):,} output tokens", "",
        f"**Target (set before the run):** label accuracy at least {pct(m['target_label_accuracy'])}. "
        f"**Result: {pct(m['label_accuracy'])}. {'Target met.' if m['meets_target'] else 'Target not met.'}**", "",
        "| Measure | Result |", "| --- | --- |",
        f"| Label accuracy (clarification vs possible change) | {pct(m['label_accuracy'])} |",
        f"| Change recall (real changes flagged) | {pct(m['change_recall'])} ({c['true_change_flagged']}/{c['true_change_flagged'] + c['missed_change']}) |",
        f"| Change precision (flags that were real changes) | {pct(m['change_precision'])} |",
        f"| Notice rule correct (6.2 a/b/c/d), on flagged real changes | {pct(m['notice_rule_accuracy'])} ({m['rule_scored_on']}) |",
        f"| Notice date correct: model's own date | {pct(m['deadline_accuracy_model_date'])} |",
        f"| Notice date correct: computed in code from the model's rule | {pct(m['deadline_accuracy_code_date'])} |",
        f"| Citation validity (quote found word for word) | {pct(m['citation_validity'])} |",
        f"| Accuracy on the {m['tricky_cases']} tricky cases | {pct(m['tricky_accuracy'])} |",
        "", "| | Predicted change | Predicted clarification |", "| --- | --- | --- |",
        f"| **Real change** | {c['true_change_flagged']} | {c['missed_change']} (missed) |",
        f"| **Real clarification** | {c['false_alarm']} (false alarm) | {c['true_clarification']} |",
        "", "## Cases that went wrong", "",
    ]
    bad = [t for t in result["trace"] if t["outcome"] != "correct"]
    for t in bad:
        e, a = t["expected"], t["model"]
        lines.append(f"- **{t['id']}** ({t['outcome']}): expected {e['label']} / {e['notice_rule']} / {e['notice_due']}; "
                     f"model said {a.get('label')} / {a.get('notice_rule')} / {a.get('notice_due')} "
                     f"(code-computed {t['computed_notice_due']}). Model's reasoning: {a.get('reasoning')}")
    if not bad:
        lines.append("None.")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="A", choices=["A", "B"])
    ap.add_argument("--run", default=None)
    ap.add_argument("--target", type=float, default=0.85)
    args = ap.parse_args()
    data = ROOT / "data" if args.set == "A" else ROOT / "data" / "set_b"
    out = ROOT / "results" if args.set == "A" else ROOT / "results" / "set_b"
    cases = json.loads((data / "cases.json").read_text())["cases"]
    key = json.loads((data / "answer_key.json").read_text())["cases"]
    run = json.loads(Path(args.run or out / "classifications.json").read_text())
    result = evaluate(cases, key, run, args.target)
    result["meta"] = run.get("meta", {})
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(result, run.get("meta", {}), out / "evaluation_report.md")
    m = result["metrics"]
    print(f"Label accuracy: {pct(m['label_accuracy'])} (target {pct(m['target_label_accuracy'])}) -> {'MET' if m['meets_target'] else 'NOT MET'}")
    print(f"Change recall {pct(m['change_recall'])}, precision {pct(m['change_precision'])}, rule {pct(m['notice_rule_accuracy'])}, "
          f"date model {pct(m['deadline_accuracy_model_date'])} vs code {pct(m['deadline_accuracy_code_date'])}")
    print(f"Report: {out / 'evaluation_report.md'}")


if __name__ == "__main__":
    main()
