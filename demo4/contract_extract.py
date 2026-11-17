#!/usr/bin/env python3
"""Read a contract's pricing and time terms, with every value tied to a real sentence.

How it stays honest (the "pick from real options, prove it with a quote" rule):
  1. Code splits the contract into numbered sentences and remembers each one's section.
  2. For each term, code finds the few sentences that could state it (keyword retrieval).
  3. The local model may only CHOOSE one of those sentence ids, or "none", and copy the value.
     Its output is constrained to those ids, so it cannot invent a clause.
  4. Code checks that the chosen sentence actually contains the value. If not, the term is marked
     "check this" for a person; if the model chose "none", it is "not stated".
  5. Optionally the model reads it several times; if the readings disagree, the term is marked "check this".
A person confirms every term before the checks use it.

Used by serve_local.py (POST /api/contract {"text": ...}). Command line:
    python3 demo4/contract_extract.py contract.md [--runs 3]
    python3 demo4/contract_extract.py --retrieval-test   (no model: are the right sentences found?)
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")
MODEL = os.environ.get("LOCAL_MODEL", "llama3.1:8b")

FEE_ON = ["CM direct costs", "subcontractor quotes", "NSS items", "SGC items", "bond and insurance", "B&O tax", "permit fees", "extended SGC (time)"]
FEE_WORDS = {"CM direct costs": ["cost of the work", "cm direct", "direct cost", "cm's own"], "subcontractor quotes": ["subcontract"],
             "NSS items": ["nss", "non-standard"], "SGC items": ["sgc", "general conditions"], "bond and insurance": ["bond", "insurance"],
             "B&O tax": ["b&o", "business and occupation"], "permit fees": ["permit"], "extended SGC (time)": ["extended"]}
NUM, BOOL = {"type": "number"}, {"type": "boolean"}

# key, plain label, kind, retrieval keywords, question for the model
TERMS = [
    ("markup_own_pct", "Sub markup on its own work", "pct", ["markup", "own work", "subcontractor", "self-performed"], "the maximum markup percent a subcontractor may add on its own work"),
    ("markup_lower_pct", "Sub markup on lower-tier work", "pct", ["markup", "lower-tier", "lower tier", "sub-subcontractor"], "the maximum markup percent on lower-tier subcontractor work"),
    ("markup_total_pct", "Total sub markup cap", "pct", ["markup", "total", "combined", "in no event", "aggregate"], "the cap on total combined markup percent"),
    ("fee_pct", "CM fee", "pct", ["fee", "percent", "%"], "the CM's Fee percent on changes"),
    ("fee_allowed_on", "Fee allowed on", "fee_on", ["fee", "may add", "direct cost", "markups", "no fee", "of a change"], "which cost categories the Fee may be charged on"),
    ("labor_burden_pct", "Labor burden", "pct", ["burden", "labor", "payroll", "fringe"], "the labor burden percent added to wages"),
    ("blue_book_pct", "Owned equipment rate", "pct", ["blue book", "equipment", "rental rate"], "the maximum percent of the Blue Book rate for CM-owned equipment"),
    ("approval_limit", "Owner's rep approval limit", "money", ["approve", "authority", "representative", "up to", "limit"], "the dollar amount above which the Owner's Representative cannot approve a change"),
    ("notice_days_standard", "Notice window (RFI, directions, site conditions)", "days", ["notice", "days", "rfi", "direction", "concealed", "receives", "response", "asi", "submittal"], "the number of days to give notice after an RFI response, direction, or concealed condition"),
    ("notice_days_other", "Notice window (other events)", "days", ["notice", "days", "other event", "should have known", "any other"], "the number of days to give notice for any other event"),
    ("contract_days", "Contract time", "days", ["substantial completion", "days", "notice to proceed", "contract time"], "the number of days to reach Substantial Completion"),
    ("liquidated_damages_per_day", "Liquidated damages", "money", ["liquidated", "each day", "per day", "damages"], "the liquidated damages per day of late completion"),
    ("daily_delay_rate", "Daily rate for extended general conditions", "money", ["daily rate", "per day", "extension", "general conditions", "extended"], "the daily rate paid for extended general conditions when contract time is extended"),
    ("sgc_total", "General conditions total", "money", ["general conditions", "sgc", "is $", "lump sum"], "the total amount of the general conditions"),
    ("extension_requires_critical_path", "Extension needs the critical path", "bool", ["critical path", "extension", "time extension", "extended only"], "whether a time extension requires the delay to be on the critical path"),
    ("compensable_causes", "Delays that earn money", "parties", ["compensated", "compensable", "caused by", "owner", "architect"], "which parties' delays are compensated with money"),
    ("concurrent_delay", "Concurrent delay", "concurrent", ["concurrent"], "how concurrent delay is treated"),
]
PARTIES = ["owner", "architect"]
CONCURRENT = ["time_no_money", "no_time_no_money", "apportioned", "not_stated"]
CAUSES = ["RFI response", "ASI", "Submittal return", "Owner direction", "Architect direction", "Concealed condition", "Other event"]


def sentences(text):
    """Split a contract into sentences, each with the section it belongs to."""
    out, sec, parent = [], "", ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^#+\s*(Article|Exhibit)\s+([A-Z0-9]+)", line)
        if m:
            sec = parent = ("Exhibit " if m.group(1) == "Exhibit" else "Art. ") + m.group(2)
            continue
        m = re.match(r"^[-*]?\s*\**\s*(\d+(?:\.\d+){1,3})\b", line)
        if m:
            sec = parent = m.group(1)
        m = re.match(r"^[-*]\s*\(([a-z])\)", line)
        if m and re.match(r"\d", parent or ""):
            sec = parent + "(" + m.group(1) + ")"
        clean = re.sub(r"[*_`#]", "", line).strip(" -")
        for part in re.split(r"(?<=[.;])\s+(?=[A-Z(])", clean):
            part = part.strip()
            if len(part) > 12 and not re.match(r"^\(?[\d.a-z]+\)?\s+[A-Z][\w'&, -]{0,60}\.$", part):
                out.append({"id": "S%d" % (len(out) + 1), "text": part, "section": sec})
    return out


def headings(text):
    """Section number -> the words around it that the sentence split drops (e.g. '3.3 Liquidated damages.')."""
    out, sec = {}, ""
    for raw in text.splitlines():
        line = re.sub(r"[*_`#]", "", raw).strip(" -")
        m = re.match(r"^(\d+(?:\.\d+){1,3})\s+(.{0,80})", line)
        if m:
            sec = m.group(1)
            out[sec] = (out.get(sec, "") + " " + m.group(2)).strip()
    return out


def context_for(sentence, sents, heads):
    """What the term-word check may read besides the sentence: its section heading and the section's first sentence."""
    if sentence is None:
        return ""
    sec = sentence.get("section") or ""
    parent = sec.split("(")[0]
    first = next((x["text"] for x in sents if x["section"] in (sec, parent)), "")
    return " ".join([heads.get(parent, ""), heads.get(sec, ""), first])


def candidates(sents, keywords, k=6, numeric=True):
    scored = []
    for s in sents:
        t = s["text"].lower()
        score = sum(2 for w in keywords if w in t)
        if numeric and re.search(r"\d", t):
            score += 1
        if score >= (3 if numeric else 2):
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:k]]


def numbers_in(text):
    return {float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


# A number only counts if its sentence is about this term: each term has words that must appear with it.
# (any-of groups; every group must match). Learned from the first run: a "25%" in a sentence about
# self-performed work passed for sub markup because the check only looked for the number.
TERM_WORDS = {
    "markup_own_pct": [["markup", "mark-up", "overhead and profit"]],
    "markup_lower_pct": [["markup", "mark-up", "overhead and profit"], ["lower", "sub-sub", "tier"]],
    "markup_total_pct": [["markup", "mark-up", "overhead and profit"], ["total", "combined", "aggregate", "in no event", "cumulative", "all tiers"]],
    "fee_pct": [["fee"]],
    "labor_burden_pct": [["burden", "payroll", "fringe"]],
    "blue_book_pct": [["blue book", "rental rate"]],
    "approval_limit": [["approv", "authori", "execute", "sign"]],
    "notice_days_standard": [["notice", "notify"]],
    "notice_days_other": [["notice", "notify"]],
    "contract_days": [["substantial completion", "contract time"]],
    "liquidated_damages_per_day": [["liquidated"]],
    "daily_delay_rate": [["day", "daily", "diem"], ["general conditions", "extended", "delay", "extension"]],
    "sgc_total": [["general conditions", "sgc"]],
}

# Word answers are never taken on the model's say-so: fixed phrase rules read the same sentence,
# and only a match is shown as verified.
NEG = r"(?:other than|except|not|excluding|but not)\s+(?:by\s+)?(?:the\s+)?"


def rule_concurrent(t):
    if re.search(r"apportion", t):
        return "apportioned"
    if re.search(r"neither\b.{0,60}\b(?:extension|time)|no (?:time )?extension\b.{0,40}\bno (?:additional )?compensation", t):
        return "no_time_no_money"
    if re.search(r"(?:extension of (?:the contract )?time|time extension|additional time|\btime\b)\b.{0,80}\b(?:but|without)\b.{0,30}\b(?:no|not|without)?\s*(?:additional )?(?:compensation|cost|money|payment)", t):
        return "time_no_money"
    return None


def rule_parties(t):
    found = []
    for p in ("owner", "architect"):
        pos = [m.start() for m in re.finditer(p, t)]
        good = [i for i in pos if not re.search(NEG + r"$", t[max(0, i - 40):i])]
        if good and re.search(r"(caused by|delay(?:s|ed)? (?:caused )?by|attributable to|responsibility of|fault of|act or omission of)", t):
            found.append(p)
    return found or None


def rule_bool_cp(t):
    if "critical path" in t and re.search(r"\b(only|solely|unless|shall not|will not|no extension|provided that|if and only)\b", t):
        return True
    return None


def verify(key, kind, value, sentence, context=""):
    """Does the chosen sentence actually say this? Returns (ok, note). context: the sentence's section heading
    and the section's first sentence, so a list item like '(a) seven days after...' still counts as about notice."""
    if sentence is None:
        return False, "not stated"
    t = sentence["text"].lower()
    tc = t + " " + (context or "").lower()
    if kind in ("pct", "money", "days"):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False, "no value"
        if v not in numbers_in(sentence["text"]):
            return False, "value not in the sentence"
        missing = [g[0] for g in TERM_WORDS.get(key, []) if not any(w in tc for w in g)]
        if missing:
            return False, "the sentence doesn't mention " + " or ".join(missing)
        return True, "value found in a sentence about this term"
    if kind == "fee_on":
        return False, "categories need a person to confirm"
    if kind == "parties":
        r = rule_parties(t)
        if r is None:
            return False, "no rule could read which parties; confirm"
        return (sorted(r) == sorted(value or []), "matches the sentence" if sorted(r) == sorted(value or []) else "the sentence reads as: " + ", ".join(r))
    if kind == "concurrent":
        r = rule_concurrent(t)
        if r is None:
            return False, "no rule could read the treatment; confirm"
        return (r == value, "matches the sentence" if r == value else "the sentence reads as: " + r.replace("_", " "))
    if kind == "bool":
        r = rule_bool_cp(t)
        if r is None:
            return False, "no rule could read it; confirm"
        return (r == value, "matches the sentence" if r == value else "the sentence reads as: yes")
    return False, "unknown kind"


def value_schema(kind):
    if kind == "fee_on":
        return {"type": "array", "items": {"type": "string", "enum": FEE_ON}}
    if kind == "parties":
        return {"type": "array", "items": {"type": "string", "enum": PARTIES}}
    if kind == "concurrent":
        return {"type": "string", "enum": CONCURRENT}
    if kind == "bool":
        return BOOL
    return NUM


def build_request(sents):
    props, lines, cands = {}, [], {}
    for key, label, kind, kw, q in TERMS:
        c = candidates(sents, kw, numeric=kind in ("pct", "money", "days"))
        cands[key] = c
        ids = [s["id"] for s in c] + ["none"]
        props[key] = {"type": "object", "properties": {"sentence": {"type": "string", "enum": ids}, "value": value_schema(kind)}, "required": ["sentence", "value"]}
        lines.append(f"## {key}: {q}\n" + ("\n".join(f"{s['id']}: {s['text']}" for s in c) or "(no candidate sentences)"))
    schema = {"type": "object", "properties": props, "required": list(props)}
    system = ("You read construction contracts. For each term below, choose the ONE sentence id that states it and copy the value "
              "exactly as written (percent as a number like 10, dollars as a number like 250000, days as a number). "
              "If none of the listed sentences states the term, choose \"none\". Never use a sentence that is not listed. Do not calculate.")
    return system, "\n\n".join(lines), schema, cands


def call(system, user, schema, model=MODEL, host=HOST):
    body = {"model": model, "stream": False, "format": schema, "keep_alive": "2h",
            "options": {"temperature": 0.2, "num_ctx": 12288, "num_predict": 1500},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(host + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1200) as r:
        return json.loads(json.loads(r.read())["message"]["content"])


def resolve(raws, cands, sents, heads=None):
    by_id = {s["id"]: s for s in sents}
    heads = heads or {}
    out = {}
    for key, label, kind, _, _ in TERMS:
        picks = [r.get(key) or {} for r in raws]
        first = picks[0]
        sid = first.get("sentence", "none")
        s = by_id.get(sid) if sid != "none" else None
        ok, note = verify(key, kind, first.get("value"), s, context_for(s, sents, heads))
        agree = all(json.dumps(p, sort_keys=True) == json.dumps(first, sort_keys=True) for p in picks)
        status = "not_stated" if s is None else "verified" if ok and agree else "check"
        if s is not None and ok and not agree:
            note = f"the {len(raws)} readings disagreed"
        out[key] = {"label": label, "kind": kind, "value": first.get("value") if s is not None else None, "quote": s["text"] if s else None,
                    "section": s["section"] if s else None, "status": status, "note": note}
    return out


def to_terms(read):
    """Reading -> the contract-terms object the checks use (docs/demo4-spec.md section 3)."""
    t = {k: {"value": v["value"], "quote": v["quote"], "section": v["section"], "status": v["status"]} for k, v in read.items()
         if k not in ("notice_days_standard", "notice_days_other")}
    std, oth = read["notice_days_standard"], read["notice_days_other"]
    if std["value"] is not None or oth["value"] is not None:
        by = {c: std["value"] for c in CAUSES[:-1]}
        by["Other event"] = oth["value"] if oth["value"] is not None else std["value"]
        t["notice_days_by_cause"] = {"value": by, "quote": std["quote"], "section": (std["section"] or "").split("(")[0],
                                     "status": "verified" if std["status"] == oth["status"] == "verified" else "check"}
    return t


def extract(text, model=MODEL, host=HOST, runs=1):
    sents = sentences(text)
    system, user, schema, cands = build_request(sents)
    t0 = time.time()
    raws = [call(system, user, schema, model, host) for _ in range(max(1, runs))]
    read = resolve(raws, cands, sents, headings(text))
    return {"read": read, "terms": to_terms(read), "model": model, "runs": runs, "seconds": round(time.time() - t0, 1),
            "sentences": len(sents)}


def retrieval_test():
    """No model needed: for each contract in the answer key, is the key's quote among the candidates code finds?"""
    key = json.loads((ROOT / "demo4" / "data" / "contract_terms_key.json").read_text())
    key = key.get("contracts", key)
    files = {"A": ROOT / "demo1" / "data" / "synthetic_contract.md", "B": ROOT / "demo4" / "data" / "contract_b.md"}
    report = {}
    for name, path in files.items():
        if not path.exists() or name not in key:
            continue
        sents = sentences(path.read_text())
        _, _, _, cands = build_request(sents)
        terms = key[name]["terms"] if "terms" in key[name] else key[name]
        hits, rows = 0, []
        for k, _, _, _, _ in TERMS:
            kk = "notice_days_by_cause" if k.startswith("notice_days") else k
            want = (terms.get(kk) or {}).get("quote")
            if not want:
                continue
            w = re.sub(r"[*_`]", "", want).strip()
            found = any(w[:60] in s["text"] or s["text"][:60] in w for s in cands[k])
            hits += found
            rows.append((k, found))
        report[name] = {"found": hits, "of": len(rows), "missed": [k for k, f in rows if not f]}
    print(json.dumps(report, indent=1))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--retrieval-test", action="store_true")
    a = ap.parse_args()
    if a.retrieval_test:
        return retrieval_test()
    text = Path(a.file).read_text()
    print(json.dumps(extract(text, a.model, runs=a.runs), indent=1))


if __name__ == "__main__":
    sys.exit(main() and 0)
