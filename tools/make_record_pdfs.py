# Prints the sample project's contracts and specs as PDF files, so the app can open "the original" the way it would
# for a real project. Every page is stamped SYNTHETIC. Writes record/files/*.pdf and record/files/index.json
# (document key -> file). python3 tools/make_record_pdfs.py   (needs reportlab)
import json, os, re
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from xml.sax.saxutils import escape

OUT = 'record/files'; os.makedirs(OUT, exist_ok=True)
ss = getSampleStyleSheet()
H = ParagraphStyle('h', parent=ss['Heading1'], fontName='Times-Bold', fontSize=15, leading=19, spaceAfter=8)
S = ParagraphStyle('s', parent=ss['Normal'], fontName='Times-Bold', fontSize=11, leading=14, spaceBefore=8)
B = ParagraphStyle('b', parent=ss['Normal'], fontName='Times-Roman', fontSize=10.5, leading=14, spaceAfter=4)
STAMP = 'SYNTHETIC. Written with AI assistance for UW INFO 492 C research. Not a real contract, firm or project.'

def page(title):
    def draw(c, d):
        c.saveState(); c.setFont('Helvetica', 7.5); c.setFillGray(0.35)
        c.drawString(0.75 * inch, 0.5 * inch, STAMP); c.drawRightString(7.75 * inch, 0.5 * inch, 'Page %d' % d.page)
        c.drawString(0.75 * inch, 10.6 * inch, title[:110]); c.restoreState()
    return draw

def md(s):  # minimal markdown: **bold**, drop > quote marks
    s = escape(s.lstrip('> ').strip())
    return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)

def write(name, title, flow):
    path = os.path.join(OUT, name)
    doc = SimpleDocTemplate(path, pagesize=letter, leftMargin=0.9 * inch, rightMargin=0.9 * inch, topMargin=0.9 * inch, bottomMargin=0.8 * inch, title=title, author='ClauseStream sample (synthetic)')
    doc.build([Paragraph(escape(title), H)] + flow, onFirstPage=page(title), onLaterPages=page(title))
    return '/' + path

idx = {}
B_ = json.load(open('record/bundle.json'))
for d in B_['documents']:
    if d['kind'] not in ('contract', 'spec'): continue
    flow = [Paragraph(escape(STAMP), B), Spacer(1, 6)]
    for p in d['pieces']:
        if p.get('section'): flow.append(Paragraph(escape(str(p['section'])), S))
        flow.append(Paragraph(escape(p['body']), B))
    slug = re.sub(r'[^a-z0-9]+', '-', (d['number'] or d['title']).lower()).strip('-')
    idx[d['key']] = write(slug + '.pdf', (d['number'] + ' · ' if d['number'] else '') + d['title'], flow)
PL = json.load(open('record/platform/platform.json'))
for k in PL['contracts']:
    if not k.get('file') or not os.path.exists(k['file']): continue
    flow = []
    for line in open(k['file']).read().split('\n'):
        if not line.strip(): continue
        if line.startswith('#'): flow.append(Paragraph(md(line.lstrip('# ')), S if line.startswith('##') else H))
        else: flow.append(Paragraph(md(re.sub(r'^[-*]\s+', '', line)), B))
    idx['k:' + k['key']] = write(os.path.basename(k['file']).replace('.md', '.pdf'), k['title'], flow)
json.dump(idx, open(os.path.join(OUT, 'index.json'), 'w'), indent=1)
print(len(idx), 'PDFs in', OUT)
