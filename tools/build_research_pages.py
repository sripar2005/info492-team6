# Builds research/personas/ and research/feedback/ in the research site's style (shell taken from research/index.html).
# python3 tools/build_research_pages.py
import re, html
src = open('research/index.html').read()
head = src[:src.index('<div style="margin-top:10px">')]
foot = src[src.index('<footer'):]
E = html.escape
BC = "font:600 13px 'Barlow Condensed', 'Arial Narrow', sans-serif; color:#616161"

def sheet(inner, top=10):
    return ('<div style="margin-top:%dpx"><div class="graph" style="position:relative; border:2.5px solid #000000; box-shadow:6px 6px 0 -1px #EDEDED, 6px 6px 0 0 #000000, 12px 12px 0 -1px #D6D6D6, 12px 12px 0 0 #000000; padding:clamp(28px,4vw,56px); color:#000000">'
            '<div aria-hidden="true" style="position:absolute; inset:14px; border:1px solid #000000; pointer-events:none"></div>%s</div></div>' % (top, inner))

def page(title, label, h1, lede, sections, path):
    out = head.replace('<title>Research · ClauseStream</title>', '<title>%s · ClauseStream</title>' % E(title))
    top = ('<div style="%s">%s</div><h1 style="margin:6px 0 0; font-size:clamp(32px,4.2vw,50px); line-height:1.04; letter-spacing:-0.02em">%s</h1>'
           '<p style="margin:10px 0 0; font-size:16px; line-height:1.55; color:#3A3A3A; max-width:760px">%s</p>'
           '<p style="margin:14px 0 0; font-size:15px"><a href="/research/">Back to the research</a></p>') % (BC, E(label), E(h1), lede)
    out += sheet(top) + ''.join(sheet(s, 40) for s in sections) + foot
    open(path, 'w').write(out)

def ul(items): return '<ul style="margin:6px 0 0; padding-left:20px; line-height:1.55">' + ''.join('<li style="margin:3px 0">%s</li>' % i for i in items) + '</ul>'
def block(h, body): return '<div style="margin-top:18px"><b style="font-size:16px">%s</b>%s</div>' % (E(h), body)

# ---------- personas (by role only) ----------
P = [
 ('GC/CM project manager', 'Primary user. Works for the general contractor / construction manager on a public school modernization (GC/CM delivery).',
  ['Collects subcontractor quotes, prices change proposals, gives notice, and keeps the schedule.',
   'Sends proposals up to the architect and owner’s rep, and gets them back with comments.'],
  ['Proposals come back for another round over fees, markups or missing backup, which costs weeks.',
   'A delay claim needs proof: was the work on the critical path, and what does a day cost?',
   'The record is spread across Procore, email, meeting minutes and spreadsheets.',
   'Firms are wary of sending contracts to cloud AI.'],
  ['Check a proposal against the contract before sending it, with each problem tied to a clause.',
   'Draft from the project record, with every citation checked.',
   'A delay check against the schedule, and cost per day from the schedule of values and general conditions.',
   'One thread per change with the subs, the architect and the owner.'],
  'Signs in as the GC/CM, puts the sub’s price into CP-0212, lets the AI draft it, confirms the numbers, runs the checks, explains the $210 fee finding, and sends it.',
  'The class visit from a CM at a large general contractor (data-sharing concerns); the owner’s-rep interviews (what makes proposals come back); industry research on change-order revisions.'),
 ('Subcontractor project manager', 'Second user. Runs a specialty trade (in the sample, an abatement subcontractor) under the GC/CM.',
  ['Prices its own work and sends change requests to the GC/CM.', 'Its crew finds conditions in the field first.'],
  ['Notice windows in the subcontract can be shorter than what the GC/CM has under the prime contract, so the sub’s claim can arrive too late.',
   'Field notes get lost between the crew and the office.',
   'It can’t see where its request stands once the GC/CM has it.',
   'Its pricing is its own business: other subs and the owner shouldn’t see it.'],
  ['A field link the crew can use from a phone, with no account.',
   'A simple request that starts the notice clock from the day it happened.',
   'Status it can see, and nothing it shouldn’t.'],
  'Signs in as the abatement sub, turns the foreman’s field note into a change request, sends it to the GC/CM, and sees that the GC/CM’s proposal and other subs’ prices are hidden.',
  'Industry research on subcontractor friction (flow-down notice terms, visibility); the owner’s-rep interviews on how sub pricing is reviewed.'),
 ('Owner’s rep', 'Reviewer and decider, on the owner’s side of a public school district. Not one of the assignment’s two personas, but the person every proposal has to satisfy, and our main stakeholder.',
  ['Reviews each change against the contract and the schedule, back-checks it, and recommends approval.',
   'Works for a public agency, so the project records are open to public disclosure.'],
  ['Delay and general-conditions costs are hard to quantify, and claims follow (worse on hard-bid than on GC/CM or design-build).',
   'Architect and owner review times can themselves delay the work.',
   'AI tools need to meet safety and privacy expectations; firms look for certifications.'],
  ['Is the delay on the critical path? Measured against the latest schedule update.',
   'What a day of delay costs, from the schedule of values and general conditions.',
   'Review clocks from the contract, and a receipt for every AI step.'],
  'Signs in as the owner’s rep, opens CP-0230, sees the proposal with a summary of the sub requests (not each sub’s pricing), decides, and checks the activity log and AI receipts.',
  'Two interviews with an owner’s rep for a school district (mid-quarter, and a review of the Demo 3 prototype).'),
]
secs = []
for name, who, does, pains, needs, demo, basis in P:
    secs.append('<div style="%s">Persona</div><h2 style="margin:4px 0 0; font-size:30px; letter-spacing:-0.01em">%s</h2><p style="margin:8px 0 0; font-size:16px; line-height:1.55; color:#3A3A3A; max-width:820px">%s</p>' % (BC, E(name), E(who)) +
                '<div class="two" style="display:grid; grid-template-columns:1fr 1fr; gap:10px 36px">' +
                block('What they do', ul(map(E, does))) + block('Where it hurts', ul(map(E, pains))) + block('What they need from ClauseStream', ul(map(E, needs))) + block('What they do in the demo', '<p style="margin:6px 0 0; line-height:1.55">%s</p>' % E(demo)) + '</div>' +
                '<p style="margin:18px 0 0; font-size:14px; color:#616161"><b>Based on:</b> %s Named by role only.</p>' % E(basis))
page('Personas', 'Who the demo is built for', 'Personas', 'The two personas the demo is built around, the GC/CM project manager and the subcontractor project manager, plus the owner’s rep every proposal has to satisfy. Built from our stakeholder interviews and research; people are named by role only.', secs, 'research/personas/index.html')

# ---------- feedback rounds ----------
R = [
 ('Round 1', 'Mid-quarter interview · owner’s rep for a school district', 'Before Demo 3',
  ['Contract rules can be checked: markups “are defined. If they’re not defined in the contract, there’s a problem.”', 'People still decide; the agent’s output feeds his review.', '“Garbage in, garbage out”: inputs decide everything.',
   'Pricing math is already solved by his tool; the costly disputes are delays, site conditions and permitting.'],
  ['Demo 3 followed his review steps: cover sheet, backup tie-out, markups against contract limits, scope match.', 'A “needs a person” route for delay, site conditions and permitting.', 'Our edge moved earlier and contract-specific: every flag quotes the clause behind it.']),
 ('Round 2', 'Class visit · CM from a large general contractor', 'Between Demo 3 and Demo 4',
  ['Firms have data-sharing concerns about sending contracts and project records to cloud AI.'],
  ['The AI runs on the user’s own device (free local models through Ollama). No API keys, nothing sent to a cloud provider.', 'Every AI step logs a receipt: model, citations, and who accepted it.']),
 ('Round 3', 'Demo 3 prototype review · owner’s rep for a school district', 'Before Demo 4 (recorded with permission)',
  ['Liked the two-step check (confirm the numbers, then check), and the whole team “literally working off the same pages.”', '“I’d much rather have a not return something with comments than return it.”',
   'Next layer of value: schedule. Is the change on the critical path? Use a baseline schedule and its updates.', 'Work out what a day of delay costs from the schedule of values and general conditions.',
   'Review delays by the architect or owner are a real source of claims.', 'Asked about AI safety standards and certifications, and a direct Procore link.', 'Pointed us to public records for real data: public contracting documents can be requested.'],
  ['Demo 4 delay check: time impact against the latest schedule update not already including the change, critical path only.', 'Cost per day from the contract’s stated rate, shown next to the schedule-of-values general-conditions spread.',
   'Baseline schedule plus updates; review clocks from the contract (architect 14 days, RFI 10 days).', 'The platform: one record from sub to owner, visibility following the contract chain.',
   'Kept the two-step check, and made it required before a proposal can be sent.', 'Procore: copy-paste today; a connector is planned (not built).', 'Real data: public RFI logs and contracts from state agencies, used for the Demo 4 evaluation.']),
]
secs = []
for n, who, when, said, changed in R:
    secs.append('<div style="%s">%s · %s</div><h2 style="margin:4px 0 0; font-size:28px; letter-spacing:-0.01em">%s</h2>' % (BC, E(n), E(when), E(who)) +
                '<div class="two" style="display:grid; grid-template-columns:1fr 1fr; gap:10px 36px">' + block('What they said', ul(map(E, said))) + block('What we changed', ul(map(E, changed))) + '</div>')
page('Stakeholder feedback', 'How feedback changed the system', 'Stakeholder feedback, round by round', 'Each round: who gave feedback, what they said, and what we changed because of it. Stakeholders are named by role only.', secs, 'research/feedback/index.html')

# ---------- Demo 4: one page with everything ----------
GH = 'https://github.com/sripar2005/info492-team6'
def h2(label, title, sub=''):
    return ('<div style="%s">%s</div><h2 style="margin:4px 0 0; font-size:30px; letter-spacing:-0.01em">%s</h2>' % (BC, E(label), E(title)) +
            ('<p style="margin:8px 0 0; font-size:16px; line-height:1.55; color:#3A3A3A; max-width:820px">%s</p>' % sub if sub else ''))
def rows(items):
    return ('<div style="margin-top:20px; border:1.5px solid #000000; background:#FFFFFF">' +
            ''.join('<a href="%s"%s style="display:flex; gap:16px; flex-wrap:wrap; align-items:baseline; padding:13px 18px; text-decoration:none; color:#000000;%s"><b style="font-size:16.5px; min-width:250px">%s</b><span style="color:#3A3A3A; font-size:15px">%s</span></a>'
                    % (href, ' target="_blank" rel="noopener"' if href.startswith('http') else '', '' if i == 0 else ' border-top:1px solid #000000;', E(t), E(d))
                    for i, (t, d, href) in enumerate(items)) + '</div>')
def para(t): return '<p style="margin:12px 0 0; font-size:16px; line-height:1.6; max-width:820px">%s</p>' % t
TBL = 'width:100%; border-collapse:collapse; margin-top:18px; background:#FFFFFF; font-size:15px'
TD = 'border:1px solid #000000; padding:9px 12px; text-align:left; vertical-align:top'

S = []
# 1. everything, mapped to the brief
S.append(h2('Start here', 'Everything for Demo 4', 'Each item the Demo 4 brief asks for, and where to find it.') + rows([
    ('Landing page', 'What ClauseStream is, in one screen', '/'),
    ('Sign in with role selection', 'Choose general contractor, subcontractor, architect or owner', '/app/#start'),
    ('Dashboard, signed in', 'Each role gets its own Home on the sample project; switch roles from “Signed in as”', '/app/'),
    ('Agent runs on real industry data', '173 public RFIs with their official answers; three free models compared', '/app/#runs'),
    ('Results summary', 'The numbers and what they mean, on this page', '#results'),
    ('Stakeholder feedback, Demo 3 and Demo 4', 'Each round: what they said and what we changed', '#feedback'),
    ('Personas', 'GC/CM project manager, subcontractor project manager, owner’s rep (by role only)', '/research/personas/'),
    ('Demo note', 'Persona, what changed since Demo 3, what it tests about the thesis (under 500 words)', '#note'),
    ('GitHub repo', 'Code, data, prompts and dependencies', '#repo'),
]))
# 2. walkthrough
steps = [
    ('Landing page.', 'The problem in one line: stop chasing paper; one record, sub to owner.'),
    ('Get started, choose a role.', 'Pick General contractor. Each role gets its own Home; the Guide button walks you through it.'),
    ('Home and Changes.', 'Open CP-0212. Amber is waiting on you, green is approved or verified, blue is written by the AI.'),
    ('Contracts.', 'Click a § link in a change, then “Read the full contract” and “Open the original file”.'),
    ('Switch role.', 'Signed in as: Subcontractor, then Owner. Same record; each sees only what their contract allows.'),
    ('07 Agent runs.', 'The results table, then one RFI side by side. Try the Maine garage question about temporary heat.'),
]
S.append(h2('Walkthrough', 'Try it yourself in five minutes', 'The same order we use in the live demo. The sample project runs in your browser; no account or AI model needed.') +
         '<ol style="margin:16px 0 0; padding-left:22px; line-height:1.6; font-size:16px">' + ''.join('<li style="margin:6px 0"><b>%s</b> %s</li>' % (E(a), E(b)) for a, b in steps) + '</ol>')
# 3. real-data results, read live from the saved runs
S.append('<div id="results"></div>' + h2('Agent runs on real industry data', 'Results on real public RFIs',
    'An agent answers contractors’ RFIs the way the owner or design team would: it searches the project’s own contract and spec documents, drafts a response, and quotes what it relied on. Code checks every quote word for word and compares the draft with the answer the agency actually published.') +
    para('<b>Data:</b> 173 RFIs with official answers from 6 public projects (State of Maine, State of Illinois, Roosevelt Island Operating Corp.). Public agencies must disclose these records; our owner’s-rep stakeholder pointed us to them. Downloaded with checksums, extracted by code, nothing edited by hand.') +
    '<div id="rtable" style="overflow-x:auto"><p style="margin:16px 0 0; color:#616161">Loading the latest results… If this doesn’t load, see <a href="/app/#runs">Agent runs</a>.</p></div>' +
    block('What it means for the thesis', ul([
        '<b>The agent drafts; a person decides.</b> On yes/no RFIs no model beat a rule that always answers “no”.',
        '<b>Confident is not the same as right.</b> The Maine garage RFI asked whether bidders must price temporary heat. llama3.1 said no, with a citation; the official answer said heat is required. gemma4 and qwen3.5 said the documents don’t settle it.',
        '<b>gemma4:12b is the trust pick.</b> Its quotes check out most often and it hands off when the answer needs new information, but it cites less and runs slower.',
        '<b>Newer isn’t automatically better.</b> qwen3.5:9b did not beat the older llama3.1:8b.',
        '<b>Limits.</b> Small subsets for yes/no, new-information and spec-section measures; bid-phase RFIs only; one prompt; word overlap is a rough measure.'])) +
    '<p style="margin:16px 0 0; font-size:15px"><a href="/app/#runs">See each RFI side by side, with the agent’s quotes checked</a></p>' +
    """<script>
(function(){
  var M=[['citations_verified','Quotes found word for word in the documents',null],['answers_fully_supported','Answers where every quote checks out',null],
    ['answers_with_citations','Answers that cite anything',null],['decision_agreement','Yes/no matches the official answer','decision_n'],
    ['new_information_flagged','Handed to a person when the answer needed new information','new_information_n'],
    ['reference_resolution','Spec sections found and cited','reference_n'],['answer_overlap_f1','Wording overlap with the official answer (F1, 0 to 1)',null],
    ['median_seconds_per_rfi','Median seconds per RFI (GitHub, no GPU)',null]];
  var hi={median_seconds_per_rfi:0};
  function f(k,v){if(v==null)return '—';if(k==='answer_overlap_f1')return v.toFixed(2);if(k==='median_seconds_per_rfi')return Math.round(v)+' s';return Math.round(v*100)+'%';}
  fetch('/data/real/results/summary.json',{cache:'no-store'}).then(function(r){return r.json();}).then(function(S){
    var ms=Object.keys(S.models),c=S.compared_on||{},b=S.baselines||{};
    var base={decision_agreement:b.decision_always_no!=null?Math.round(b.decision_always_no*100)+'% (always “no”)':(b.decision_always_yes!=null?Math.round(b.decision_always_yes*100)+'% (always “yes”)':'—'),
      reference_resolution:'',answer_overlap_f1:''};
    var m0=S.models[ms[0]]; base.reference_resolution=m0.reference_resolution_top_search_result!=null?Math.round(m0.reference_resolution_top_search_result*100)+'% (keyword search)':'—';
    base.answer_overlap_f1=m0.answer_overlap_f1_baseline_top_search_text!=null?m0.answer_overlap_f1_baseline_top_search_text.toFixed(2)+' (top search result)':'—';
    var TD='TDS';
    var h='<p style="margin:16px 0 0;font-size:16px;line-height:1.55"><b>Compared on the same '+(c.rfis||m0.rfis_run)+' RFIs</b> <span style="color:#616161">(the ones every model finished'+(c.projects?', from '+c.projects.length+' of '+S.projects.length+' projects':'')+'). Best result in each row in bold.</span></p>';
    h+='<table style="TBLS"><thead><tr><th style="'+TD+'">Measure</th>'+ms.map(function(m){return '<th style="'+TD+'">'+m+'</th>';}).join('')+'<th style="'+TD+'">No AI baseline</th></tr></thead><tbody>';
    M.forEach(function(x){var k=x[0],vals=ms.map(function(m){return S.models[m][k];}),ok=vals.filter(function(v){return v!=null;});
      var best=k==='median_seconds_per_rfi'?null:Math.max.apply(null,ok);
      var n=x[2]?S.models[ms[0]][x[2]]:null;
      h+='<tr><td style="'+TD+'"><b>'+x[1]+'</b>'+(n!=null?' <span style="color:#616161">('+n+' RFIs)</span>':'')+'</td>'+vals.map(function(v){return '<td style="'+TD+(v===best?';font-weight:700':'')+'">'+f(k,v)+'</td>';}).join('')+'<td style="'+TD+'">'+(base[k]||'—')+'</td></tr>';});
    document.getElementById('rtable').innerHTML=h+'</tbody></table>';
  }).catch(function(){});
})();
</script>""".replace('TDS', TD).replace('TBLS', TBL))
# 4. synthetic tests
S.append(h2('Also tested', 'The contract and delay checks, on synthetic data',
    'These test the product’s other AI steps against an answer key. The data is synthetic, written by our team with AI assistance, and every PDF is stamped synthetic. Model: llama3.1:8b, 3 runs each.') +
    '<table style="%s"><thead><tr><th style="%s">Test</th><th style="%s">Tuned on</th><th style="%s">Held out</th></tr></thead><tbody>' % (TBL, TD, TD, TD) +
    '<tr><td style="%s"><b>Contract terms read correctly</b> (markups, fees, notice, approval limits)</td><td style="%s">15 of 16 (contract A)</td><td style="%s">12 of 15 (contract C); 1 confidently wrong</td></tr>' % (TD, TD, TD) +
    '<tr><td style="%s"><b>Delay check: days of delay exactly right</b></td><td style="%s">10 of 10 change orders</td><td style="%s">2 of 5 change orders</td></tr>' % (TD, TD, TD) +
    '<tr><td style="%s"><b>Product checks vs answer key</b> (code only, no AI)</td><td style="%s" colspan="2">107 of 107 right</td></tr></tbody></table>' % (TD, TD) +
    para('Every term the AI reads is shown with the sentence it came from, and a person confirms it before any check uses it. Details: <a href="%s/tree/main/demo4" target="_blank" rel="noopener">demo4 in the repo</a>.' % GH))
# 5. feedback
fb = [('Round 1, before Demo 3', 'Owner’s rep, school district', 'Contract rules can be checked; people still decide.', 'Demo 3 followed his review steps, with a “needs a person” route.'),
      ('Round 2, between Demo 3 and 4', 'CM from a large general contractor (class visit)', 'Firms won’t send contracts to cloud AI.', 'The AI runs on free local models; every AI step logs a receipt.'),
      ('Round 3, Demo 3 review', 'Owner’s rep, school district', 'Liked the whole team working off the same pages; next value is schedule; pointed us to public records.', 'One record from sub to owner, the delay check, and the real-data evaluation.'),
      ('Round 4, Demo 4 live demo', 'Stakeholders at the November 20 demo', 'Added after the demo.', '—')]
S.append('<div id="feedback"></div>' + h2('Stakeholder feedback', 'How feedback shaped Demo 3 and Demo 4', 'Named by role only. The full rounds, with quotes, are on the <a href="/research/feedback/">feedback page</a>.') +
    '<div style="overflow-x:auto"><table style="%s"><thead><tr><th style="%s">Round</th><th style="%s">Who</th><th style="%s">What they said</th><th style="%s">What we changed</th></tr></thead><tbody>' % (TBL, TD, TD, TD, TD) +
    ''.join('<tr><td style="%s"><b>%s</b></td><td style="%s">%s</td><td style="%s">%s</td><td style="%s">%s</td></tr>' % (TD, E(a), TD, E(b), TD, E(c), TD, E(d)) for a, b, c, d in fb) + '</tbody></table></div>')
# 6. demo note
note = open('research/demo4_note.md').read().strip()
def md(t):
    t = E(t); t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t); return t
blocks, cur = [], []
for line in note.split('\n'):
    if line.startswith('- '): cur.append(md(line[2:]))
    else:
        if cur: blocks.append(ul(cur)); cur = []
        if line.strip(): blocks.append(para(md(line)))
if cur: blocks.append(ul(cur))
S.append('<div id="note"></div>' + h2('Demo note', 'Demo 4 note', '%d words.' % len(note.split())) + ''.join(blocks))
# 7. repo
S.append('<div id="repo"></div>' + h2('Repository', 'Code, data, prompts, dependencies', 'Everything is in <a href="%s" target="_blank" rel="noopener">github.com/sripar2005/info492-team6</a>.' % GH) + rows([
    ('Real-data evaluation code', 'tools/real: fetch, extract, run, score', GH + '/tree/main/tools/real'),
    ('Real data', 'data/real: 67 source PDFs with checksums, 173 extracted RFIs, saved runs and scores', GH + '/tree/main/data/real'),
    ('Agent prompt (real RFIs)', 'The system prompt is in tools/real/rfi_eval.py and saved with every run', GH + '/blob/main/tools/real/rfi_eval.py'),
    ('Product agent prompts', 'demo3/prompts: one per role, plus the shared system prompt', GH + '/tree/main/demo3/prompts'),
    ('Product code', 'app, assets: the platform, role dashboards, contract reader', GH + '/tree/main/assets'),
    ('Dependencies', 'requirements.txt (Python) and Ollama for the free local models', GH + '/blob/main/requirements.txt'),
    ('How to run it', 'README: tests, database, reproducing the evaluation', GH + '#readme'),
]))
page('Demo 4', 'Demo 4 · live demo November 20, 2026', 'Demo 4: one record, sub to owner',
     'ClauseStream keeps one record of every change, RFI and contract from subcontractor to owner, and an AI agent drafts from it with every quote checked. This page has everything for Demo 4: the product, the agent results on real data, the stakeholder feedback, the demo note and the code.',
     S, 'research/demo4/index.html')
print('ok')
