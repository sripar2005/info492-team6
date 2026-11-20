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
print('ok')
