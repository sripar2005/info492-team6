# Pulls real RFIs (question + the official published answer) out of the public records in data/real/pdf/,
# and splits each project's contract and spec documents into citable pieces.
# Writes data/real/rfis.json and data/real/docs/<project>.json. Nothing is hand-edited: rerun to reproduce.
#   python3 tools/real/extract.py            (needs pdftotext from poppler-utils)
import json, os, re, subprocess, hashlib

ROOT = 'data/real/pdf'

def text(path):
    return subprocess.run(['pdftotext', '-layout', path, '-'], capture_output=True, text=True).stdout

def clean(s):
    s = re.sub(r'[​﻿]', '', s)
    s = re.sub(r'[ \t]+', ' ', s)
    return re.sub(r'\s*\n\s*', ' ', s).strip()

# ---------- family A: "1. question ... A. answer" ----------
def numbered(t, start=None, stop=None, ans=r'(?:A\.|a\.\s*Response\s*[-–:]|Response\s*[-–:]|Answer\s*[-–:]?)'):
    if start:
        m = re.search(start, t)
        if not m: return []
        t = t[m.end():]
    if stop:
        m = re.search(stop, t)
        if m: t = t[:m.start()]
    blocks = re.split(r'\n\s{0,8}(\d{1,3})\.\s+', '\n' + t)
    out = []
    for i in range(1, len(blocks) - 1, 2):
        n, body = int(blocks[i]), blocks[i + 1]
        m = re.search(r'\n\s*' + ans + r'\s*', body)
        if not m: continue
        q, a = clean(body[:m.start()]), clean(body[m.end():])
        a = re.split(r'\s(?:Page \d+ of \d+|END OF)\b', a)[0]
        if len(q) > 15 and a: out.append({'n': n, 'question': q, 'answer': a})
    return out

# ---------- family B: ruled tables, read cell by cell from the PDF ----------
def ruled(path, q_col=1, a_col=2, disc_col=None):
    import pdfplumber
    out, seen = [], set()
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            for t in pg.extract_tables():
                for row in t:
                    if not row or not (row[0] or '').strip().isdigit(): continue
                    n = int(row[0].strip())
                    q, a = clean(row[q_col] or ''), clean(row[a_col] or '') if a_col < len(row) else ''
                    if n in seen or len(q) < 15 or not a: continue
                    seen.add(n)
                    r = {'n': n, 'question': q, 'answer': a}
                    if disc_col is not None and disc_col < len(row): r['discipline'] = clean(row[disc_col] or '')
                    out.append(r)
    return out

# ---------- family C: "Q. question / A. answer", unnumbered ----------
def qa(t):
    out = []
    for i, m in enumerate(re.finditer(r'\nQ\.\s+(.*?)\nA\.\s+(.*?)(?=\nQ\.\s|\Z)', '\n' + t, re.S)):
        q, a = clean(m.group(1)), clean(m.group(2))
        if len(q) > 15 and a: out.append({'n': i + 1, 'question': q, 'answer': a})
    return out

# The projects in the evaluation: each has an RFI log with published answers AND contract/spec text to cite.
P = [
 {'id': 'maine-2995-capitol-garage', 'name': 'Capitol Parking Garage 2026 Repairs (State of Maine BGS #2995)', 'owner': 'State of Maine, Bureau of General Services',
  'rfis': [('2995_Addendum_1_DAFS.pdf', lambda p: numbered(text(p), start=r'RFIS:'))],
  'docs': ['2995_Addendum_1_DAFS.pdf']},
 {'id': 'illinois-uic-cancer-pavilion', 'name': 'Drug Discovery and Cancer Research Pavilion, UIC (Illinois CDB #830-030-167), design-build', 'owner': 'Illinois Capital Development Board',
  'rfis': [(f, lambda p: numbered(text(p))) for f in ['rfi-responses-5-12-26.pdf', 'RFI_Responses_August_26.pdf', 'RFI_Responses_10-16-26.pdf']],
  'docs': ['00_830-030-167_Request_for_Proposals_-_FINAL.pdf', '12_01_11_01_-_SP_Supplement_to_SD-DB_3.2017.pdf']},
 {'id': 'illinois-niccs-design-build', 'name': 'Northern Illinois Center for Community Sustainability (Illinois CDB #822-010-135), design-build', 'owner': 'Illinois Capital Development Board',
  'rfis': [(f, lambda p: numbered(text(p))) for f in ['RFIs_Phase_I-_August_20.pdf', 'December_31_2025_RFIs.pdf', 'January_8_2026_RFIs.pdf']],
  'docs': ['Request_for_Proposal.pdf', '10.01_11_01_-_SP_Supplement_to_SD-DB_3.2017.pdf']},
 {'id': 'illinois-idot-materials-lab', 'name': 'IDOT Materials Lab (Illinois CDB #630-442-057), design-build', 'owner': 'Illinois Capital Development Board',
  'rfis': [('630-442-057-phase-i-rfis.pdf', lambda p: qa(text(p)))],
  'docs': ['01.630-442-057-rfp.pdf']},
 {'id': 'maine-3843-wellness-center', 'name': 'Wellness Center Re-Use Renovation (State of Maine BGS #3843)', 'owner': 'State of Maine, Bureau of General Services',
  'rfis': [('3843_Addendum_2_DAFS.pdf', lambda p: ruled(p, 1, 3, 2))],
  'docs': ['3843_Project_Manual_DAFS.pdf', '3843_Addendum_1_DAFS.pdf']},
 {'id': 'ny-rioc-eleanors-pier', 'name': 'Eleanor’s Pier Repair (Roosevelt Island Operating Corp. RFP #26-1095)', 'owner': 'Roosevelt Island Operating Corporation',
  'rfis': [('Addenda_2-_RFI_log_and_due_date_extension.pdf', lambda p: ruled(p, 1, 2))],
  'docs': ['RFP_26_1095_Eleanors_Pier_Repair_Project-1.pdf', 'RIOC_Standard_Form_Contract_for_Construction.pdf']},
]

# ---------- contract and spec pieces: split on section headings so a citation can name a section ----------
HEAD = re.compile(r'^\s{0,12}((?:SECTION|Section|ARTICLE|Article)\s+(?:\d{2} ?\d{2} ?\d{2}|[\dA-Z][\w.]{0,8})|\d{1,2}(?:\.\d{1,2}){1,3}|[A-Z]\.\d+|\d{2} \d{2} \d{2}(?:\.\d+)?)\s*[-–:]?\s+([A-Z][^\n]{2,90})$', re.M)
RUNNING = re.compile(r'^.{20,}\s{6,}(\d{2}) (\d{2}) (\d{2})\s*$', re.M)   # a spec number in a page header or footer
def csi_of(label):
    m = re.search(r'(\d{2}) ?(\d{2}) ?(\d{2})', label)
    return ''.join(m.groups()) if m and not re.fullmatch(r'\d{1,2}(\.\d+)+', label.strip()) else None

def pieces(doc, t):
    out, last, pos, csi = [], ('Front matter', ''), 0, None
    for m in HEAD.finditer(t):
        body = t[pos:m.start()]
        run = RUNNING.findall(body)
        if run: csi = ''.join(run[-1])
        if len(clean(body)) > 60: out.append((last, body, csi))
        last, pos = (m.group(1).strip(), clean(m.group(2))[:90]), m.start()
        csi = csi_of(last[0]) or csi            # the spec section (e.g. 00 72 13) a sub-heading sits in
    out.append((last, t[pos:], csi))
    res = []
    for (sec, title), body, csi in out:
        b = clean(body)
        for k in range(0, len(b), 1600):   # long sections are split into ~1,600-character parts, same section label
            part = b[k:k + 1700]
            pid = '%s#%s#%d' % (doc, sec, k // 1600)
            res.append({'id': hashlib.sha1(pid.encode()).hexdigest()[:10], 'doc': doc, 'section': sec, 'csi': csi, 'title': title, 'text': part})
    return res

def main():
    os.makedirs('data/real/docs', exist_ok=True)
    allr, summary = [], []
    for p in P:
        d = os.path.join(ROOT, p['id'])
        got = []
        for f, fn in p['rfis']:
            for r in fn(os.path.join(d, f)):
                r.update(project=p['id'], source=f, id='%s:%s:%d' % (p['id'], f.split('.')[0][:28], r['n']))
                got.append(r)
        docs = []
        for f in p['docs']:
            docs += pieces(f, text(os.path.join(d, f)))
        json.dump({'project': p['id'], 'name': p['name'], 'owner': p['owner'], 'pieces': docs}, open('data/real/docs/%s.json' % p['id'], 'w'), indent=0)
        allr += got
        summary.append({'project': p['id'], 'name': p['name'], 'rfis': len(got), 'pieces': len(docs)})
        print('%-32s %3d RFIs  %5d document pieces' % (p['id'], len(got), len(docs)))
    json.dump({'note': 'Real RFIs and their official published answers, extracted by tools/real/extract.py from the public records in data/real/pdf/ (sources and checksums: data/real/manifest.json). Not edited by hand.',
               'projects': summary, 'rfis': allr}, open('data/real/rfis.json', 'w'), indent=1)
    print('total', len(allr))

if __name__ == '__main__':
    main()
