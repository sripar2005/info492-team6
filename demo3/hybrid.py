#!/usr/bin/env python3
"""Two-tier review: computed checks and inferred checks, labeled and scored separately.

Demo 3 asked whether agents catch contract violations at the handoff. The answer we measured was
mixed in a way that a single percentage hides: the arithmetic checks were perfect and the agent
judgment was noisy. Averaging those two into one score tells a reviewer nothing about which flags
to trust.

So this composes the two and keeps them labeled:

  Tier 1  COMPUTED   A number, a date, or a signature is out of bounds. Derived from a structured
                     field by rules.py, with the arithmetic shown. Fires identically every run.
                     Measured on our 36 cases: 23 of 33 issues, 0 false alarms, 0 clean proposals
                     flagged, 6 of 6 escalations routed to a person.

  Tier 2  INFERRED   What a line item means: is this cost already covered by the Fee, is the work
                     really a change, is this equipment an Exhibit B or C item. Also anything
                     stated only in an email quote the calculator could not parse. Decided by the
                     agents. Higher recall, and noisy: presented as leads to check, never as
                     findings.

A reviewer reads Tier 1 as settled and Tier 2 as a worklist. Our stakeholder back-checks his
tools by hand, so the useful thing is not a higher score, it is knowing which half needs the
back-check.

No new model calls: Tier 2 comes from an agent run already saved and published, unchanged.

Honest note on ordering. The arithmetic/judgment split came from our stakeholder before we ran
anything ("the AI does a really nice job of recognizing the math") and the Washington State
Auditor's change order guidance independently tells owners to "recalculate overhead and markup
calculations." But assigning these specific flag types this way was decided after seeing which
types each system handled well. This is therefore a second system scored beside the first, not a
correction to it. The Demo 3 numbers stand as reported. Cases, answer key, and agent prompts were
not touched.

Usage:
  python hybrid.py                 two-tier run -> results/hybrid/runs.json
  python hybrid.py --curve         print the precision/recall tradeoff table
"""
import argparse
import json
from pathlib import Path

import rules

ROOT = Path(__file__).resolve().parent

# Types the agents own, because each turns on meaning rather than on a number.
MODEL_TYPES = {"COVERED_COST", "NOT_A_CHANGE", "EQUIPMENT"}

# How strict to be about an agent flag before showing it. Defaults chosen for the demo: show
# agent leads, but only when the agent quoted the contract and the quote verified word for word.
DEFAULTS = {"require_verified_quote": True, "min_agents": 1}


def load_run(path):
    return {r["id"]: r for r in json.loads(Path(path).read_text())["results"]}


def agent_votes(code_env, model_result, require_verified_quote, min_agents):
    """Agent flags eligible for Tier 2, with the roles that raised each one."""
    unparsed = bool(code_env["unparsed_quotes"])
    code_types = {f["type"] for f in code_env["flags"]}
    votes, set_aside = {}, []
    for env in model_result["trail"]:
        role = env.get("from_role")
        for f in env["flags"]:
            t = f.get("type")
            if not (t in MODEL_TYPES or unparsed):
                set_aside.append({"type": t, "role": role, "reason": "a computed check owns this"})
                continue
            if t in code_types and t not in MODEL_TYPES:
                set_aside.append({"type": t, "role": role, "reason": "already computed"})
                continue
            if require_verified_quote and not f.get("quote_verified"):
                set_aside.append({"type": t, "role": role, "reason": "contract quote did not verify"})
                continue
            v = votes.setdefault(t, {"roles": set(), "flag": f})
            v["roles"].add(role)
    kept = {t: v for t, v in votes.items() if len(v["roles"]) >= min_agents}
    for t, v in votes.items():
        if t not in kept:
            set_aside.append({"type": t, "role": ",".join(sorted(x or "?" for x in v["roles"])),
                              "reason": f"only {len(v['roles'])} agent(s) raised it"})
    return kept, set_aside


def combine(cp_id, code_result, model_result, require_verified_quote=True, min_agents=1):
    code_env = code_result["trail"][0]
    kept, set_aside = agent_votes(code_env, model_result, require_verified_quote, min_agents)

    computed = [{**f, "tier": "computed"} for f in code_env["flags"]]
    inferred, seen = [], {f["type"] for f in computed}
    for t, v in sorted(kept.items()):
        if t in seen and t not in MODEL_TYPES:
            continue
        if t in seen:
            continue
        seen.add(t)
        inferred.append({**v["flag"], "tier": "inferred", "tier_note": "agent judgment, needs review",
                         "raised_by": sorted(x or "?" for x in v["roles"])})

    route = ("ESCALATE" if seen & rules.FORCE_ESCALATE else "RETURN" if seen else "APPROVE")
    env = {"envelope_id": f"{cp_id}-hybrid", "from_role": "hybrid",
           "authority": "code computes, agents judge, a person decides",
           "decision": {"APPROVE": "PASS"}.get(route, route),
           "flags": computed + inferred,
           "computed_count": len(computed), "inferred_count": len(inferred),
           "agent_flags_set_aside": len(set_aside),
           "unparsed_quotes": code_env["unparsed_quotes"],
           "model": "computed checks + agent judgment"}
    return {"id": cp_id, "route": route, "trail": [env]}


def build(cases, model, **kw):
    code = {c["id"]: rules.check(c) for c in cases}
    return [combine(c["id"], code[c["id"]], model[c["id"]], **kw) for c in cases]


def curve(cases, model, key):
    """The tradeoff table. Shows that with a small local model there is no free lunch."""
    from evaluate import score
    rows = [("computed checks only", {"only_code": True})]
    rows += [("+ agent leads, any quote", {"require_verified_quote": False, "min_agents": 1}),
             ("+ verified quote required", {"require_verified_quote": True, "min_agents": 1}),
             ("+ two agents must agree", {"require_verified_quote": False, "min_agents": 2}),
             ("+ verified and two agents", {"require_verified_quote": True, "min_agents": 2}),
             ("+ verified and three agents", {"require_verified_quote": True, "min_agents": 3})]
    out = []
    for label, kw in rows:
        if kw.pop("only_code", False):
            results = [rules.check(c) for c in cases]
        else:
            results = build(cases, model, **kw)
        m = score({"results": results}, key)["metrics"]
        out.append({"configuration": label, "caught": m["issues_caught"], "of": m["seeded_issues"],
                    "detection_rate": round(m["detection_rate"], 3),
                    "clean_flagged": m["clean_cases_flagged"], "clean_total": m["clean_cases"],
                    "false_alarms": m["extra_flags"], "routes_right": m["routes_right"],
                    "escalation_recall": m["escalation_recall"], "tricky_right": m["tricky_right"]})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model-run", default="results/local/llama3.1-8b/runs.json")
    p.add_argument("--out", default="results/hybrid/runs.json")
    p.add_argument("--curve", action="store_true", help="print and save the tradeoff table")
    a = p.parse_args()

    cases = json.loads((ROOT / "data" / "cases.json").read_text())["cases"]
    model = load_run(ROOT / a.model_run)

    if a.curve:
        key = json.loads((ROOT / "data" / "answer_key.json").read_text())["cases"]
        rows = curve(cases, model, key)
        path = ROOT / "results" / "tradeoff.json"
        path.write_text(json.dumps({"model_run": a.model_run, "rows": rows}, indent=1))
        w = max(len(r["configuration"]) for r in rows)
        print(f"{'configuration'.ljust(w)}  caught        clean flagged  false alarms")
        for r in rows:
            print(f"{r['configuration'].ljust(w)}  {r['caught']:2d}/{r['of']} ({r['detection_rate']:.0%})"
                  f"   {r['clean_flagged']:2d}/{r['clean_total']}          {r['false_alarms']:3d}")
        print(f"\nSaved {path}")
        return

    results = build(cases, model, **DEFAULTS)
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": {"backend": "hybrid", "model": "computed checks + agent judgment",
                                        "model_run": a.model_run, "agents_own": sorted(MODEL_TYPES),
                                        "gate": DEFAULTS},
                               "results": results}, indent=1))
    c = sum(r["trail"][0]["computed_count"] for r in results)
    i = sum(r["trail"][0]["inferred_count"] for r in results)
    print(f"Saved {out}  (computed flags {c}, inferred flags {i})")


if __name__ == "__main__":
    main()
