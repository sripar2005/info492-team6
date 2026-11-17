#!/usr/bin/env python3
"""Read a change proposal's text into the check form's fields, using a free local model (Ollama).

The model only copies numbers and dates from the document into named fields. It does not judge or
compute anything; the contract checks run afterwards in code, and a person confirms every field
first. Missing numbers come back as 0 and missing text as "", and the form asks the person to check
them.

Used by serve_local.py (POST /api/extract with {"text": ...}). Can also be run directly:
    python3 demo3/extract.py file.pdf [file2.pdf ...]
    python3 demo3/extract.py --test          (runs on check/samples/*.pdf, writes results/extract_test.json)
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")
MODEL = os.environ.get("LOCAL_MODEL", "llama3.1:8b")

CAUSES = ["RFI response", "ASI", "Submittal return", "Owner direction", "Architect direction", "Concealed condition", "Other event"]
FEE_ON = ["CM direct costs", "subcontractor quotes", "NSS items", "SGC items", "bond and insurance", "B&O tax", "permit fees", "extended SGC (time)"]
NUM, STR, BOOL = {"type": "number"}, {"type": "string"}, {"type": "boolean"}


def obj(props):
    return {"type": "object", "properties": props, "required": list(props)}


SCHEMA = obj({
    "id": STR, "title": STR, "cause": {"type": "string", "enum": CAUSES + [""]}, "cause_ref": STR,
    "event_date": STR, "notice_date": STR, "time_days": NUM,
    "subs": {"type": "array", "items": obj({
        "firm": STR, "trade": STR, "email_only": BOOL, "own_cost": NUM, "own_markup_pct": NUM, "lower_cost": NUM,
        "lower_markup_pct": NUM, "quote_total": NUM, "breakdown": BOOL,
        "tm_tags": {"type": "array", "items": obj({"tag": STR, "date": STR, "signed_by_cm": BOOL, "signed_by_owner": BOOL})}})},
    "cm_direct": NUM,
    "labor": {"type": "array", "items": obj({"desc": STR, "hours": NUM, "wage": NUM, "burden_pct": NUM})},
    "equipment": {"type": "array", "items": obj({"desc": STR, "hours": NUM, "rate": NUM, "blue_book": NUM})},
    "nss": NUM, "sgc": NUM, "bond": NUM, "bo": NUM, "permits": NUM, "ext_sgc": NUM,
    "fee_pct": NUM, "fee_on": {"type": "array", "items": {"type": "string", "enum": FEE_ON}}, "fee_amount": NUM, "total": NUM,
})

SYSTEM = """You copy numbers and dates from a construction change proposal into JSON fields. Copy exactly what the
document states. Do not calculate, correct, or judge anything. If a value is not stated, use 0 for numbers,
"" for text, false for yes/no, and [] for lists.

Fields:
- id: the change proposal number, like "CP-0212". title: its title.
- cause: the type of cause, one of the allowed values. cause_ref: the reference text.
- event_date, notice_date: dates as YYYY-MM-DD. time_days: calendar days of time extension requested.
- subs: one entry per subcontractor quote. firm, trade.
  email_only: true when the quote is only the text of an email (then fill quote_total and leave the rest 0).
  own_cost: "cost of own work before markup". own_markup_pct: the percent in "Markup on own work (N%)".
  lower_cost: "lower-tier subcontractors, total". lower_markup_pct: the percent in "Markup on lower-tier work (N%)".
  quote_total: "QUOTE TOTAL". breakdown: true if itemized lines are listed, false for a lump sum with no breakdown.
  tm_tags: each time-and-material tag, with whether it is signed by the CM superintendent and by the Owner's representative.
- cm_direct: cover sheet "CM direct costs".
- labor: each CM labor line with hours, wage, and labor burden percent (e.g. 32 for 32%).
- equipment: only CM-owned equipment that shows a "rate charged" and a "Blue Book rate"; skip rented equipment.
- Cover sheet amounts: nss = non-standard services (NSS), sgc = specified general conditions (SGC), bond = bond and
  insurance, bo = B&O tax, permits = permit fees, ext_sgc = extended general conditions (time).
- fee_pct: the CM Fee percent (5 for 5%). fee_on: every item the fee line says it is applied to. fee_amount: the fee in dollars.
- total: TOTAL REQUESTED.
Reply with only the JSON object."""


def call(text, model=MODEL, host=HOST, retries=2):
    body = {"model": model, "stream": False, "format": SCHEMA, "keep_alive": "2h",
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 1500},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "DOCUMENT TEXT:\n\n" + text[:20000]}]}
    last = None
    for _ in range(retries + 1):
        try:
            t0 = time.time()
            req = urllib.request.Request(host + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=900) as r:
                out = json.loads(r.read())
            return json.loads(out["message"]["content"]), round(time.time() - t0, 1)
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"Local model call failed: {last}")


def to_form(raw):
    """Model output -> the check form's fields (the same names assets/checks.js uses)."""
    num = lambda x: float(x) if isinstance(x, (int, float)) else 0.0  # noqa: E731
    subs = []
    for s in raw.get("subs") or []:
        if s.get("email_only"):
            subs.append({"firm": s.get("firm", ""), "trade": s.get("trade", ""), "email_only": True, "quote_total": num(s.get("quote_total"))})
            continue
        subs.append({"firm": s.get("firm", ""), "trade": s.get("trade", ""), "email_only": False, "own_cost": num(s.get("own_cost")),
                     "own_markup_pct": num(s.get("own_markup_pct")), "lower_cost": num(s.get("lower_cost")),
                     "lower_markup_pct": num(s.get("lower_markup_pct")), "breakdown": bool(s.get("breakdown")),
                     "quote_total": num(s.get("quote_total")),
                     "tm_tags": [{"tag": t.get("tag", ""), "date": t.get("date", ""), "signed": bool(t.get("signed_by_cm")) and bool(t.get("signed_by_owner"))}
                                 for t in s.get("tm_tags") or []]})
    form = {"id": raw.get("id", ""), "title": raw.get("title", ""), "cause": raw.get("cause") if raw.get("cause") in CAUSES else "",
            "cause_ref": raw.get("cause_ref", ""), "event_date": raw.get("event_date", ""), "notice_date": raw.get("notice_date", ""),
            "time_days": num(raw.get("time_days")), "subs": subs, "cm_direct": num(raw.get("cm_direct")),
            "labor": [{"desc": l.get("desc", ""), "hours": num(l.get("hours")), "wage": num(l.get("wage")), "burden_pct": num(l.get("burden_pct"))} for l in raw.get("labor") or []],
            "equipment": [{"desc": e.get("desc", ""), "rate": num(e.get("rate")), "blue_book": num(e.get("blue_book")), "hours": num(e.get("hours"))}
                          for e in raw.get("equipment") or [] if num(e.get("blue_book")) > 0],
            "nss": num(raw.get("nss")), "sgc": num(raw.get("sgc")), "bond": num(raw.get("bond")), "bo": num(raw.get("bo")),
            "permits": num(raw.get("permits")), "ext_sgc": num(raw.get("ext_sgc")), "fee_pct": num(raw.get("fee_pct")),
            "fee_on": [p for p in raw.get("fee_on") or [] if p in FEE_ON], "fee_amount": num(raw.get("fee_amount")), "total": num(raw.get("total"))}
    form["sub_total"] = round(sum(s.get("quote_total", 0) for s in subs), 2)
    # Fields a person must look at: empty dates or cause, or a zero where a value is always expected.
    missing = [k for k in ("cause", "event_date", "notice_date") if not form[k]] + [k for k in ("fee_pct", "total") if not form[k]]
    return form, missing


def extract(text, model=MODEL, host=HOST):
    raw, secs = call(text, model, host)
    form, missing = to_form(raw)
    return {"form": form, "missing": missing, "model": model, "seconds": secs}


def pdf_text(path):
    from pypdf import PdfReader
    return "\n\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="*")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--model", default=MODEL)
    a = ap.parse_args()
    files = sorted((ROOT / "check" / "samples").glob("*.pdf")) if a.test else [Path(p) for p in a.pdfs]
    out = []
    for f in files:
        try:
            r = extract(pdf_text(f), a.model)
        except Exception as e:  # noqa: BLE001
            r = {"error": str(e)}
        r["file"] = f.name
        out.append(r)
        print(f.name, json.dumps(r)[:400], flush=True)
    if a.test:
        p = ROOT / "demo3" / "results" / "extract_test.json"
        p.write_text(json.dumps({"model": a.model, "results": out}, indent=1))
        print("saved", p)


if __name__ == "__main__":
    sys.exit(main())
