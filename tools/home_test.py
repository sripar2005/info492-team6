# Role Home screens: each role's numbers match what that role may see, nothing leaks across roles, and an empty
# project shows empty states without errors. Serve the site on :8765 first.   python3 tools/home_test.py
import re, sys
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765'
bad, E = [], []
def check(ok, what):
    if not ok: bad.append(what)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); pg = b.new_page(viewport={'width': 1280, 'height': 1000})
    pg.on('pageerror', lambda e: E.append(str(e)))
    pg.goto(BASE + '/app/?project=sample#home'); pg.wait_for_timeout(8000)
    for role in ['Example Builders', 'Clearwater', 'Example Architecture', 'School District']:
        v = pg.evaluate("r=>[...document.querySelectorAll('#viewas option')].find(o=>o.text.includes(r)).value", role); pg.select_option('#viewas', v); pg.wait_for_timeout(1800)
        txt = pg.inner_text('#app'); strip = pg.inner_text('.sumstrip')
        truth = pg.evaluate("""async()=>{const P=CSPlat,c=(await P.sb().from('changes').select('*').eq('project_id',P.ctx().project.id)).data.filter(P.sees.change);
          return {proposals_approved:c.filter(x=>x.tier==='proposal'&&x.status==='approved').length, with_owner:c.filter(x=>x.status==='with_owner').length,
                  with_arch:c.filter(x=>x.status==='with_architect').length, returned:c.filter(x=>x.status==='returned').length, subs:[...new Set(c.filter(x=>x.tier==='sub_request').map(x=>x.from_company))].length}}""")
        n = lambda label: int(re.search(r'([\d,]+)[^\n]*\n' + label, strip).group(1).replace(',', '')) if re.search(r'([\d,]+)[^\n]*\n' + label, strip) else None
        if role == 'Example Builders':
            check(n('returned') == truth['returned'], 'GC returned count')
        if role == 'Clearwater':
            for other in ['Summit Roofing', 'Harmony Acoustics', 'Puget Steel', 'Granite']:
                check(other not in txt, 'sub Home shows another sub: ' + other)
            check(truth['subs'] <= 1, 'sub can see other subs’ requests')
        if role == 'Example Architecture':
            check(n('in review') == truth['with_arch'], 'architect in-review count')
            check('CR-' not in txt, 'architect Home shows sub request numbers')
        if role == 'School District':
            check(n('decisions waiting') == truth['with_owner'], 'owner decisions count')
            m = re.search(r'(\d+) · \$[\d,.]+\napproved to date', strip); check(m and int(m.group(1)) == truth['proposals_approved'], 'owner approved count')
            check('CR-' not in txt, 'owner Home shows sub request numbers')
        print(role, 'ok' if not bad else bad)
    # An empty project: every role panel shows its empty state.
    pg.evaluate("""async()=>{const P=CSPlat,sb=P.sb();const r=await sb.rpc('start_project',{p_name:'Empty test',p_type:'gccm',p_company:'Test GC',p_role:'gc',p_synthetic:true});await P.openProject(r.data);}""")
    pg.evaluate("location.hash='#changes'"); pg.wait_for_timeout(800); pg.evaluate("location.hash='#home'"); pg.wait_for_timeout(2500)
    t = pg.inner_text('#app'); check('Nothing is waiting on you' in t, 'empty project: waiting list empty state'); check('No open sub requests' in t, 'empty project: subs panel empty state')
    print('empty project', 'ok' if 'Nothing is waiting on you' in t else t[:300])
    b.close()
for e in E: bad.append('script error: ' + e)
print('home tests:', 'all passed' if not bad else 'FAILED'); [print('  ' + x) for x in bad]
sys.exit(1 if bad else 0)
