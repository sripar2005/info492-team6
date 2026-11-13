#!/usr/bin/env python3
"""Demo 3: one review agent per party on each priced Change Proposal (CP).

Parties (in handoff order): subcontractor -> GC/CM -> Architect -> Owner's PM -> a person decides.
Each agent sees the CP from its own seat, gets the contract, Demo 1's rule card, and a code-computed
calculator sheet, and returns a structured review. This module wraps each review in a message
"envelope" (from, to, authority, decision, flags with quotes) and keeps an append-only audit trail.

Two back ends share the same prompts and schema:
  anthropic  Claude through the API (key from ANTHROPIC_API_KEY)
  ollama     a local model on your own computer (http://localhost:11434)

Usage:
  python agents.py --dry-run
  python agents.py                       # all 30 CPs, Claude
  python agents.py --backend ollama --model llama3.1:8b
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT.parent / "demo1"))
from common import normalize  # noqa: E402
from calc import sheet  # noqa: E402

CONTRACT_FILE = ROOT.parent / "demo1" / "data" / "synthetic_contract.md"
RULES_FILE = ROOT.parent / "demo1" / "results" / "extracted_rules.json"
CASES_FILE = ROOT / "data" / "cases.json"
PROMPTS = ROOT / "prompts"
CACHE = ROOT / "results" / "cache"
DEFAULT_MODEL = os.environ.get("DEMO3_MODEL", "claude-sonnet-5-5")

ROLES = ["sub", "gc", "architect", "owner"]
ROLE_NAMES = {"sub": "Subcontractor", "gc": "GC/CM", "architect": "Architect", "owner": "Owner's PM"}
AUTHORITY = {
    "sub": "May submit its own pricing or hold it for fixes. Cannot escalate.",
    "gc": "May send the CP to the Architect and Owner, return it to the subcontractor, or escalate to the CM Project Manager.",
    "architect": "Reviews CPs for the Owner; confirms or disputes that the work is a change. Cannot approve cost or time (Exhibit D).",
    "owner": "Recommends approval, returns with questions, or escalates to the Owner's Representative. Never approves (Exhibit D).",
}
NEXT = {  # where each decision sends the envelope
    "sub": {"PASS": "gc", "RETURN": "sub"},
    "gc": {"PASS": "architect", "RETURN": "sub", "ESCALATE": "CM Project Manager (person)"},
    "architect": {"PASS": "owner", "RETURN": "gc", "ESCALATE": "Architect (person)"},
    "owner": {"PASS": "Owner's Representative (person): recommend approval", "RETURN": "gc",
              "ESCALATE": "Owner's Representative (person): decision needed"},
}
FLAG_TYPES = ["SUB_MARKUP", "FEE_RATE", "FEE_ON_EXCLUDED", "COVERED_COST", "EQUIPMENT", "LABOR_BURDEN", "TIEOUT",
              "MISSING_BACKUP", "LATE_NOTICE", "NOT_A_CHANGE", "TIME_IMPACT", "CONCEALED_CONDITION", "OVER_AUTHORITY"]
RULE_CARD_TYPES = {"fee_rate", "fee_exclusion", "markup_limit", "non_chargeable_cost", "equipment_rule", "pricing_input",
                   "approval_authority", "notice_window", "waiver_consequence", "documentation_requirement", "amount", "cap"}


def tool_schema(role):
    decisions = ["PASS", "RETURN"] if role == "sub" else ["PASS", "RETURN", "ESCALATE"]
    return {
        "name": "record_review",
        "description": "Record this party's review of the Change Proposal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "enum": decisions},
                "flags": {"type": "array", "items": {"type": "object", "properties": {
                    "type": {"type": "string", "enum": FLAG_TYPES},
                    "section": {"type": "string", "description": "Deciding contract section, e.g. '6.5.2'."},
                    "quote": {"type": "string", "description": "Exact phrase (5-30 words) copied from the contract."},
                    "amount_at_issue": {"type": ["number", "null"]},
                    "explanation": {"type": "string"},
                }, "required": ["type", "section", "quote", "explanation"]}},
                "message": {"type": "string", "description": "Plain message to the next party (2-4 sentences)."},
                "escalation_reason": {"type": ["string", "null"]},
            },
            "required": ["decision", "flags", "message"],
        },
    }


def rule_card():
    rules = json.loads(RULES_FILE.read_text(encoding="utf-8"))["rules"]
    keep = [r for r in rules if r.get("type") in RULE_CARD_TYPES and r.get("quote_verified")]
    return "\n".join(f"[{r['id']}] ({r['type']}; sec {', '.join(r.get('sections') or [])}) {r['summary']} | \"{r['quote']}\"" for r in keep)


def view_for(role, cp):
    """What each party sees. The subcontractor sees its own quotes, not the CM's lines or cover sheet."""
    if role == "sub":
        return {k: cp[k] for k in ("id", "title", "cause", "narrative", "subcontractor_quotes")}
    return cp


def build_prompt(role, cp, contract, rules):
    """System prompt and contract come first and are identical for every call, so a local model can reuse
    its cache of that prefix; the CP, calculator sheet, and role instructions come last."""
    system = (PROMPTS / "shared_system.txt").read_text().strip()
    calc = sheet(cp)
    if role == "sub":
        calc = {"subcontractors": calc["subcontractors"]}
    user = ((PROMPTS / "user.txt").read_text().replace("[[CONTRACT]]", contract).replace("[[RULES]]", rules)
            .replace("[[CP]]", json.dumps(view_for(role, cp), indent=1)).replace("[[CALC]]", json.dumps(calc, indent=1))
            .replace("[[ROLE_TEXT]]", (PROMPTS / f"role_{role}.txt").read_text().strip())
            .replace("[[ROLE_NAME]]", ROLE_NAMES[role]))
    return system, user


def call_anthropic(client, model, system, user, role, retries=3):
    last = None
    for attempt in range(1, retries + 1):
        try:
            t0 = time.time()
            r = client.messages.create(model=model, max_tokens=2000, system=system, tools=[tool_schema(role)],
                                       tool_choice={"type": "auto"}, messages=[{"role": "user", "content": user}])
            calls = [b for b in r.content if getattr(b, "type", None) == "tool_use" and b.name == "record_review"]
            if not calls:
                raise ValueError(f"no record_review call (stop_reason={r.stop_reason})")
            return dict(calls[0].input), {"input_tokens": r.usage.input_tokens, "output_tokens": r.usage.output_tokens,
                                          "latency_s": round(time.time() - t0, 2)}
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"API call failed: {last}")


OLLAMA_HOST = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")


def call_ollama(model, system, user, role, host=None, retries=2):
    """Local open model through Ollama, constrained to the same JSON schema the API agents use."""
    import urllib.request
    host = host or OLLAMA_HOST
    schema = tool_schema(role)["input_schema"]
    body = {"model": model, "stream": False, "format": schema, "keep_alive": "2h",
            "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 1200},
            "messages": [{"role": "system", "content": system + "\n\nYou cannot call tools here. Reply with only a JSON object "
                          "matching the record_review schema: decision, flags, message, escalation_reason."},
                         {"role": "user", "content": user}]}
    last = None
    for _ in range(retries + 1):
        try:
            t0 = time.time()
            req = urllib.request.Request(host + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=1800) as resp:
                out = json.loads(resp.read())
            answer = json.loads(out["message"]["content"])
            allowed = tool_schema(role)["input_schema"]["properties"]["decision"]["enum"]
            if answer.get("decision") not in allowed:
                answer["decision"] = "RETURN" if answer.get("flags") else "PASS"
            answer["flags"] = [f for f in (answer.get("flags") or []) if isinstance(f, dict) and f.get("type") in FLAG_TYPES]
            return answer, {"input_tokens": out.get("prompt_eval_count", 0), "output_tokens": out.get("eval_count", 0),
                            "latency_s": round(time.time() - t0, 2)}
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"Ollama call failed: {last}")


def review(role, cp, backend, model, client=None, contract=None, rules=None, use_cache=True):
    contract = contract or CONTRACT_FILE.read_text(encoding="utf-8")
    rules = rules if rules is not None else rule_card()
    system, user = build_prompt(role, cp, contract, rules)
    key = hashlib.sha256(f"{backend}\n{model}\n{system}\n{user}".encode()).hexdigest()[:24]
    path = CACHE / f"{key}.json"
    if use_cache and path.exists():
        c = json.loads(path.read_text())
        return c["answer"], c["usage"], True
    if backend == "anthropic":
        answer, usage = call_anthropic(client, model, system, user, role)
    else:
        answer, usage = call_ollama(model, system, user, role)
    if use_cache:
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"answer": answer, "usage": usage}, indent=1))
    return answer, usage, False


def envelope(cp, role, answer, model, norm_contract, prev_id):
    decision = answer.get("decision", "PASS")
    flags = []
    for f in answer.get("flags") or []:
        q = normalize(f.get("quote", ""))
        flags.append({**f, "quote_verified": bool(q) and len(q.split()) >= 4 and q in norm_contract})
    eid = f"{cp['id']}-{ROLES.index(role) + 1}-{role}"
    return {
        "envelope_id": eid, "cp": cp["id"], "prev_envelope_id": prev_id,
        "from_role": role, "from": ROLE_NAMES[role] + " agent",
        "to": NEXT[role].get(decision, "next party"),
        "authority": AUTHORITY[role],
        "decision": decision, "flags": flags,
        "message": answer.get("message", ""), "escalation_reason": answer.get("escalation_reason"),
        "model": model, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def system_route(envs):
    ds = [e["decision"] for e in envs]
    return "ESCALATE" if "ESCALATE" in ds else "RETURN" if "RETURN" in ds else "APPROVE"


def run_case(cp, backend, model, client=None, contract=None, rules=None, use_cache=True):
    """Run all parties' agents on one CP; returns the audit trail (list of envelopes) and the route."""
    contract = contract or CONTRACT_FILE.read_text(encoding="utf-8")
    rules = rules if rules is not None else rule_card()
    norm = normalize(contract)
    trail, prev, usage_total, cached = [], None, {"input_tokens": 0, "output_tokens": 0}, 0
    for role in ROLES:
        if role == "sub" and not cp["subcontractor_quotes"]:
            env = {"envelope_id": f"{cp['id']}-1-sub", "cp": cp["id"], "prev_envelope_id": None, "from_role": "sub",
                   "from": "Subcontractor agent", "to": "gc", "authority": AUTHORITY["sub"], "decision": "PASS", "flags": [],
                   "message": "No subcontractor pricing in this CP; the CM self-performed the work.", "escalation_reason": None,
                   "model": "none (no subcontractor quote)", "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "skipped": True}
        else:
            try:
                answer, usage, was_cached = review(role, cp, backend, model, client, contract, rules, use_cache)
                cached += int(was_cached)
                for k in usage_total:
                    usage_total[k] += usage.get(k, 0)
                env = envelope(cp, role, answer, model, norm, prev)
            except RuntimeError as e:
                # A model that returns unusable output gets no flags for this review (scored as misses), and the
                # failure is recorded in the audit trail instead of stopping the whole run.
                env = envelope(cp, role, {"decision": "PASS", "flags": [], "message": "The agent's output could not be read; a person must review this CP."}, model, norm, prev)
                env["model_error"] = str(e)[:300]
        trail.append(env)
        prev = env["envelope_id"]
    return {"id": cp["id"], "route": system_route(trail), "trail": trail, "usage": usage_total, "cached_calls": cached}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=["anthropic", "ollama"], default="anthropic")
    ap.add_argument("--model", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", nargs="*", help="CP ids to run")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    model = a.model or (DEFAULT_MODEL if a.backend == "anthropic" else "llama3.1:8b")
    slug = model.replace(":", "-").replace("/", "-")
    out = Path(a.out or (ROOT / "results" / ("runs.json" if a.backend == "anthropic" else f"local/{slug}/runs.json")))
    cases = json.loads(CASES_FILE.read_text())["cases"]
    if a.only:
        cases = [c for c in cases if c["id"] in a.only]
    contract, rules = CONTRACT_FILE.read_text(encoding="utf-8"), rule_card()
    n_calls = sum(4 if c["subcontractor_quotes"] else 3 for c in cases)
    print(f"{len(cases)} CPs, {n_calls} agent calls, backend {a.backend}, model {model}")
    if a.dry_run:
        s, u = build_prompt("owner", cases[0], contract, rules)
        print(f"owner prompt about {len(s) + len(u):,} characters; rule card {rules.count(chr(10)) + 1} rules")
        return
    client = None
    if a.backend == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("ANTHROPIC_API_KEY is not set.")
        import anthropic
        client = anthropic.Anthropic()
    workers = a.workers if a.backend == "anthropic" else 1
    results = {}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(run_case, c, a.backend, model, client, contract, rules): c["id"] for c in cases}
        for i, f in enumerate(cf.as_completed(futs), 1):
            r = f.result()
            results[r["id"]] = r
            print(f"[{i:>2}/{len(cases)}] {r['id']}: {r['route']}  " + "  ".join(
                f"{e['from_role']}={e['decision']}{'(' + ','.join(x['type'] for x in e['flags']) + ')' if e['flags'] else ''}" for e in r["trail"]))
    ordered = [results[c["id"]] for c in cases]
    meta = {"backend": a.backend, "model": model, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "cases": len(ordered), "agent_calls": n_calls,
            "input_tokens": sum(r["usage"]["input_tokens"] for r in ordered),
            "output_tokens": sum(r["usage"]["output_tokens"] for r in ordered),
            "cached_calls": sum(r["cached_calls"] for r in ordered),
            "prompt_sha256": hashlib.sha256("".join((PROMPTS / p).read_text() for p in sorted(os.listdir(PROMPTS))).encode()).hexdigest()[:16]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": meta, "results": ordered}, indent=1, ensure_ascii=False))
    print(f"Saved {out}. Next: python evaluate.py")


if __name__ == "__main__":
    main()
