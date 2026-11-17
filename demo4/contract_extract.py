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


def verify(kind, value, sentence):
    """Does the chosen sentence actually say this? Returns (ok, note)."""
    if sentence is None:
        return False, "not stated"
    t = sentence["text"].lower()
    if kind in ("pct", "money", "days"):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False, "no value"
        return (v in numbers_in(sentence["text"]), "value found in the sentence" if v in numbers_in(sentence["text"]) else "value not in the sentence")
    if kind == "fee_on":
        missing = [p for p in value or [] if not any(w in t for w in FEE_WORDS.get(p, [p.lower()]))]
        return (bool(value) and not missing, "categories found" if value and not missing else "not all categories appear in the sentence")
    if kind == "parties":
        missing = [p for p in value or [] if p not in t]
        return (bool(value) and not missing, "parties found" if value and not missing else "parties not in the sentence")
    if kind == "concurrent":
        return ("concurrent" in t, "mentions concurrent delay" if "concurrent" in t else "sentence doesn't mention concurrent delay")
    if kind == "bool":
        return ("critical path" in t, "mentions the critical path" if "critical path" in t else "sentence doesn't mention the critical path")
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


def resolve(raws, cands, sents):
    by_id = {s["id"]: s for s in sents}
    out = {}
    for key, label, kind, _, _ in TERMS:
        picks = [r.get(key) or {} for r in raws]
        first = picks[0]
        sid = first.get("sentence", "none")
        s = by_id.get(sid) if sid != "none" else None
        ok, note = verify(kind, first.get("value"), s)
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
    read = resolve(raws, cands, sents)
    return {"read": read, "terms": to_terms(read), "model": model, "runs": runs, "seconds": round(time.time() - t0, 1),
            "sentences": len(sents)}


def retrieval_test():
    """No model needed: for each contract in the answer key, is the key's quote among the candidates code finds?"""
    key = json.loads((ROOT / "demo4" / "data" / "contract_terms_key.json").read_text())
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
