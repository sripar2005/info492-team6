#!/usr/bin/env python3
"""Make sample change-proposal PDFs from the synthetic test proposals, for trying the PDF upload.

These are synthetic documents written for this project. Run from the repo root:
    python3 tools/make_samples.py      (writes check/samples/*.pdf)
"""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = {"CP-0212": "haul-off-fee-problem", "CP-0201": "roof-drains-clean", "CP-0209": "gas-shutoff-markup",
           "CP-0219": "blocking-labor-burden", "CP-0231": "plumbing-email-quote"}
FEE_WORDS = {"CM direct costs": "CM direct costs", "subcontractor quotes": "subcontractor quotes", "NSS items": "non-standard services (NSS)",
             "SGC items": "specified general conditions (SGC)", "bond and insurance": "bond and insurance", "B&O tax": "B&O tax",
             "permit fees": "permit fees", "extended SGC (time)": "extended general conditions (time)"}
ss = getSampleStyleSheet()
H, B, S = ss["Heading2"], ss["BodyText"], ss["Heading4"]


def m(x):
    return f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"


def table(rows, widths, bold_last=False):
    t = Table(rows, colWidths=widths)
    st = [("FONT", (0, 0), (-1, -1), "Helvetica", 9), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
          ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black), ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.lightgrey),
          ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    if bold_last:
        st += [("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 9), ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black)]
    t.setStyle(TableStyle(st))
    return t


def build(cp, path):
    c = cp["cover_sheet"]
    el = [Paragraph(f"CHANGE PROPOSAL {cp['id']}", H),
          Paragraph("Project: Sample school modernization (synthetic test document). From: Sample GC/CM, to: Owner's Representative.", B),
          Paragraph(f"<b>Title:</b> {cp['title']}", B), Spacer(1, 8), Paragraph("Cause", S),
          table([["Item", "Detail"], ["Type of cause", cp["cause"]["type"]], ["Reference", cp["cause"].get("reference", "")],
                 ["Date of the event", cp["cause"]["event_date"]], ["Date written notice was given", cp["notice_date"]],
                 ["Time extension requested", f"{cp['time_impact_days']} calendar days"]], [2.6 * inch, 4.2 * inch]),
          Spacer(1, 10), Paragraph("Cover sheet", S)]
    fee_on = ", ".join(FEE_WORDS.get(p, p) for p in c["fee_applied_to"])
    rows = [["Line", "Amount"], ["CM direct costs (CM labor, material, equipment)", m(c["cm_direct_costs"])],
            ["Subcontractor quotes", m(c["subcontractor_quotes"])],
            [Paragraph(f"CM Fee at {c['fee_rate'] * 100:g}%, applied to: {fee_on}", B), m(c["fee"])]]
    for label, key in [("Bond and insurance", "bond_and_insurance"), ("B&O tax", "bo_tax"), ("Permit fees", "permit_fees"),
                       ("Non-standard services (NSS)", "nss_items"), ("Specified general conditions (SGC)", "sgc_items"),
                       ("Extended general conditions (time)", "extended_sgc_time")]:
        rows.append([label, m(c[key])])
    rows.append(["TOTAL REQUESTED", m(c["total_requested"])])
    el += [table(rows, [5.2 * inch, 1.6 * inch], bold_last=True), Spacer(1, 6),
           Paragraph(f"Backup attached: {', '.join(cp.get('backup_attached', [])) or 'none listed'}.", B)]

    for q in cp["subcontractor_quotes"]:
        el += [PageBreak(), Paragraph(f"Subcontractor quote: {q['firm']} ({q.get('trade', '')})", H)]
        if q.get("format") == "email text":
            el += [Paragraph("Received by email. Text of the email:", B), Spacer(1, 4)]
            el += [Paragraph(line or "&nbsp;", B) for line in q["text"].split("\n")]
            continue
        if q["lines"]:
            rows = [["Item", "Qty", "Unit", "Rate", "Amount"]] + [[l["desc"], f"{l['qty']:g}", l["unit"], m(l["rate"]), m(l["amount"])] for l in q["lines"]]
            el.append(table(rows, [3.0 * inch, 0.7 * inch, 0.6 * inch, 1.1 * inch, 1.4 * inch]))
        else:
            el.append(Paragraph("Lump sum quote. No itemized breakdown attached.", B))
        own_pct = 100 * q["markup_on_own"] / q["own_direct"] if q["own_direct"] else 0
        rows = [["Summary", "Amount"], ["Cost of own work before markup", m(q["own_direct"])],
                [f"Markup on own work ({own_pct:g}%)", m(q["markup_on_own"])]]
        if q["lower_tier_total"]:
            for l in q["lower_tier"]:
                rows.append([f"Lower-tier subcontractor: {l['firm']} ({l['scope']})", m(l["amount"])])
            low_pct = 100 * q["markup_on_lower_tier"] / q["lower_tier_total"]
            rows += [["Lower-tier subcontractors, total", m(q["lower_tier_total"])], [f"Markup on lower-tier work ({low_pct:g}%)", m(q["markup_on_lower_tier"])]]
        rows.append(["QUOTE TOTAL", m(q["quote_total"])])
        el += [Spacer(1, 8), table(rows, [5.2 * inch, 1.6 * inch], bold_last=True)]
        if q.get("tm_tags"):
            el += [Spacer(1, 8), Paragraph("Time-and-material tags", S),
                   table([["Tag", "Date", "Signed by CM superintendent", "Signed by Owner's representative"]] +
                         [[t["tag"], t["date"], "yes" if t["signed_by_cm_superintendent"] else "NO", "yes" if t["signed_by_owner_rep"] else "NO"] for t in q["tm_tags"]],
                         [0.9 * inch, 1.1 * inch, 2.4 * inch, 2.4 * inch])]

    if cp["cm_lines"]:
        el += [PageBreak(), Paragraph("CM direct costs, detail", H)]
        lab = [l for l in cp["cm_lines"] if l["kind"] == "labor"]
        if lab:
            el += [Paragraph("Labor", S), table([["Who", "Hours", "Wage", "Labor burden", "Amount"]] +
                   [[l["desc"] + (f" ({l['person']})" if l.get("person") else ""), f"{l['hours']:g}", m(l["wage"]), f"{l['burden_rate'] * 100:g}%", m(l["amount"])] for l in lab],
                   [2.8 * inch, 0.7 * inch, 0.9 * inch, 1.0 * inch, 1.4 * inch])]
        eq = [l for l in cp["cm_lines"] if l["kind"] == "equipment"]
        if eq:
            rows = [["Equipment", "Hours", "Rate charged", "Blue Book rate", "Amount"]]
            for l in eq:
                if "blue_book_rate" in l:
                    rows.append([l["desc"], f"{l['hours_used']:g}", m(l["rate_charged"]), m(l["blue_book_rate"]), m(l["amount"])])
                else:
                    rows.append([l["desc"] + " (rented, invoice attached)", "", "", "", m(l["amount"])])
            el += [Spacer(1, 6), Paragraph("Equipment", S), table(rows, [2.8 * inch, 0.7 * inch, 1.1 * inch, 1.1 * inch, 1.1 * inch])]
        other = [l for l in cp["cm_lines"] if l["kind"] not in ("labor", "equipment")]
        if other:
            el += [Spacer(1, 6), Paragraph("Other", S), table([["Item", "Amount"]] + [[l["desc"], m(l["amount"])] for l in other], [5.2 * inch, 1.6 * inch])]

    SimpleDocTemplate(str(path), pagesize=letter, title=f"{cp['id']} {cp['title']}", leftMargin=0.8 * inch, rightMargin=0.8 * inch).build(el)


def main():
    cases = {c["id"]: c for c in json.loads((ROOT / "demo3" / "data" / "cases.json").read_text())["cases"]}
    out = ROOT / "check" / "samples"
    out.mkdir(parents=True, exist_ok=True)
    for cid, name in SAMPLES.items():
        build(cases[cid], out / f"{cid}-{name}.pdf")
        print("wrote", out / f"{cid}-{name}.pdf")


if __name__ == "__main__":
    main()
