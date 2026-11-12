#!/usr/bin/env python3
"""Score Demo 3 runs against the answer key.

Targets (set before running, from the thesis): the agents together catch at least 85% of seeded
issues; clean CPs are not flagged; every quote is real.

Usage: python evaluate.py   (scores every run file found; writes results/evaluation.json and .md)
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = 0.85
def run_files():
    """Local open-model runs first (one folder per model), then an API run if any, then the baseline."""
    runs = {f"local-{p.parent.name}": p for p in sorted((ROOT / "results" / "local").glob("*/runs.json"))}
    runs["agents"] = ROOT / "results" / "runs.json"
    runs["baseline"] = ROOT / "results" / "baseline" / "runs.json"
    return runs


def score(run, key):
    k = {c["id"]: c for c in key}
    found = total = by_resp = 0
    per_type = defaultdict(lambda: [0, 0])
    extra = 0
    route_ok = 0
    conf = Counter()
    quotes = verified = 0
    clean_flagged = clean_total = 0
    trace = []
    for r in run["results"]:
        exp = k[r["id"]]
        exp_types = {f["type"] for f in exp["expected_flags"]}
        got = defaultdict(set)  # type -> roles that flagged it
        for e in r["trail"]:
            for f in e["flags"]:
                got[f["type"]].add(e["from_role"])
                if e["from_role"] != "baseline":
                    quotes += 1
                    verified += int(f.get("quote_verified", False))
        caught, missed = [], []
        for f in exp["expected_flags"]:
            total += 1
            per_type[f["type"]][1] += 1
            if f["type"] in got:
                found += 1; per_type[f["type"]][0] += 1; caught.append(f["type"])
                by_resp += int(f["role"] in got[f["type"]] or "baseline" in got[f["type"]])
            else:
                missed.append(f["type"])
        extras = sorted(t for t in got if t not in exp_types)
        extra += len(extras)
        if not exp_types:
            clean_total += 1
            clean_flagged += int(bool(got))
        route_ok += int(r["route"] == exp["expected_route"])
        conf[(exp["expected_route"], r["route"])] += 1
        if not exp_types and not got:
            outcome = "correct: clean"
        elif not missed and not extras and r["route"] == exp["expected_route"]:
            outcome = "correct"
        elif missed:
            outcome = "missed issue"
        elif extras:
            outcome = "false alarm"
        else:
            outcome = "wrong route"
        trace.append({"id": r["id"], "expected_route": exp["expected_route"], "route": r["route"],
                      "expected": [f["type"] for f in exp["expected_flags"]], "caught": caught, "missed": missed,
                      "extra": extras, "outcome": outcome, "tricky": exp["tricky"], "why": exp["why"]})
    esc_exp = sum(1 for c in key if c["expected_route"] == "ESCALATE")
    esc_got = sum(1 for r in run["results"] if r["route"] == "ESCALATE")
    esc_hit = conf[("ESCALATE", "ESCALATE")]
    n = len(run["results"])
    det = found / total if total else 0
    return {
        "metrics": {
            "cases": n, "seeded_issues": total, "issues_caught": found, "detection_rate": det,
            "caught_by_responsible_party": by_resp, "target": TARGET, "meets_target": det >= TARGET,
            "extra_flags": extra, "clean_cases": clean_total, "clean_cases_flagged": clean_flagged,
            "route_accuracy": route_ok / n, "routes_right": route_ok,
            "escalation_recall": esc_hit / esc_exp if esc_exp else None,
            "escalation_precision": esc_hit / esc_got if esc_got else None,
            "citation_validity": (verified / quotes) if quotes else None, "quotes": quotes,
            "tricky_right": sum(1 for t in trace if t["tricky"] and t["outcome"].startswith("correct")),
            "tricky_total": sum(1 for t in trace if t["tricky"]),
            "detection_by_type": {t: {"found": v[0], "total": v[1]} for t, v in sorted(per_type.items())},
            "route_confusion": {f"{a}->{b}": c for (a, b), c in sorted(conf.items())},
        },
        "trace": trace,
    }


def main():
    key = json.loads((ROOT / "data" / "answer_key.json").read_text())["cases"]
    out = {"systems": {}}
    lines = ["# Demo 3 evaluation", ""]
    for name, path in run_files().items():
        if not path.exists():
            continue
        run = json.loads(path.read_text())
        s = score(run, key)
        s["meta"] = run.get("meta", {})
        out["systems"][name] = s
        m = s["metrics"]
        lines += [f"## {name} ({s['meta'].get('model', '')})",
                  f"- Seeded issues caught: {m['issues_caught']}/{m['seeded_issues']} ({m['detection_rate']:.1%}); target {TARGET:.0%}: {'met' if m['meets_target'] else 'not met'}",
                  f"- Caught by the responsible party: {m['caught_by_responsible_party']}/{m['seeded_issues']}",
                  f"- Routes right: {m['routes_right']}/{m['cases']}; clean CPs flagged: {m['clean_cases_flagged']}/{m['clean_cases']}; extra flags: {m['extra_flags']}",
                  f"- Citation validity: {m['citation_validity'] if m['citation_validity'] is None else format(m['citation_validity'], '.1%')} of {m['quotes']} quotes",
                  f"- Tricky cases right: {m['tricky_right']}/{m['tricky_total']}", ""]
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "evaluation.json").write_text(json.dumps(out, indent=1))
    (ROOT / "results" / "evaluation_report.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
