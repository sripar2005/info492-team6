# Navigation audit: walks every page and every app screen the way a visitor would, and reports where navigation breaks.
# Method: a link crawl of the site (every page, every internal link and asset) plus a state-flow crawl of the app
# (after Crawljax: for each party and each screen, click every control and record what changed).
# Needs the site served locally:  python3 -m http.server 8765   then   python3 tools/nav_audit.py
# Writes tools/nav_audit_report.json and prints a summary. External links are listed, not fetched.
import json, sys, time
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765'
REDIRECTS = [r['source'] for r in json.load(open('vercel.json'))['redirects']]
issues, pages, states = [], {}, []

def issue(kind, where, detail):
    issues.append({'kind': kind, 'where': where, 'detail': detail})

def is_redirect(path):
    return any(path == s or (s.endswith(':path*') and path.startswith(s.split('/:')[0] + '/')) for s in REDIRECTS)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome')

    # ---------- 1. the site: every page, every link ----------
    ctx = b.new_context(viewport={'width': 1280, 'height': 900}); pg = ctx.new_page()
    errs, bad = [], []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('response', lambda r: bad.append((r.status, r.url)) if r.status >= 400 and r.url.startswith(BASE) else None)
    queue, seen, external = ['/'], set(), set()
    while queue:
        path = queue.pop(0)
        if path in seen: continue
        seen.add(path); errs.clear(); bad.clear()
        r = pg.goto(BASE + path); pg.wait_for_timeout(1200)
        if not r or r.status >= 400:
            if not is_redirect(path): issue('broken page', path, r.status if r else 'no response')
            continue
        links = pg.eval_on_selector_all('a[href]', 'els => els.map(a => ({href: a.getAttribute("href"), text: (a.textContent || "").trim().slice(0, 40), vis: !!(a.offsetWidth || a.offsetHeight)}))')
        internal = []
        for l in links:
            h = l['href']
            if h.startswith('mailto:') or h.startswith('tel:') or h.startswith('javascript:'): continue
            u = urlparse(urljoin(BASE + path, h))
            if u.netloc and u.netloc != urlparse(BASE).netloc: external.add(urljoin(BASE + path, h)); continue
            target = u.path or '/'
            internal.append(target)
            if target.endswith('/') or target.endswith('.html'):
                if target not in seen: queue.append(target)
            else:
                rr = ctx.request.get(BASE + target)
                if rr.status >= 400 and not is_redirect(target): issue('broken link', path, '%s -> %s (%s)' % (l['text'] or h, target, rr.status))
        home = any(t == '/' for t in internal)
        pages[path] = {'links': len(internal), 'has_home_link': home, 'title': pg.title()}
        if not internal: issue('dead end', path, 'no links to anywhere else on the site')
        elif not home and not path.startswith('/app'): issue('no way home', path, 'no link back to the landing page')
        for e in errs: issue('script error', path, e)
        for s, u in bad: issue('missing file', path, '%s %s' % (s, u.replace(BASE, '')))
    ctx.close()

    # ---------- 2. the app: every screen, for every party, every control ----------
    def fresh(role=None, w=1280, h=900, start=None):
        c = b.new_context(viewport={'width': w, 'height': h}); g = c.new_page(); E = []
        g.on('pageerror', lambda e: E.append(str(e)))
        if start: g.goto(BASE + start); g.wait_for_timeout(1500); return c, g, E
        g.goto(BASE + '/app/?project=sample#home'); g.wait_for_timeout(7000)
        if role:
            v = g.evaluate("r => { const o = [...document.querySelectorAll('#viewas option')].find(o => o.text.includes(r)); return o && o.value; }", role)
            if v: g.select_option('#viewas', v); g.wait_for_timeout(1500)
        return c, g, E

    def view(g): return g.evaluate("(location.hash || '#home').slice(1).split('?')[0]")
    def text(g, sel='#app'):
        el = g.query_selector(sel); return el.inner_text() if el else ''
    def back_to_app(g, hashv):
        # A link that leaves the app (to the landing page, a research page) is fine; come back and reload the sample.
        if urlparse(g.url).path != '/app/':
            g.goto(BASE + '/app/#' + hashv); g.wait_for_timeout(7000); return True
        return False
    def close_overlays(g):
        g.evaluate("document.querySelectorAll('.modal').forEach(m => m.remove())")

    def controls(g):
        return g.evaluate("""() => {
          const els = [...document.querySelectorAll('#app a[href], #app button, #app [data-copen], #app [data-dopen], #modeband button, #modeband a, nav a, nav button, header a, .tabs a, .tabs button')];
          const out = [], seen = new Set();
          els.forEach((el, i) => {
            const r = el.getBoundingClientRect(); if (!r.width || !r.height) return;
            if (el.closest('form') && el.type === 'submit') return;
            const key = (el.tagName + '|' + (el.getAttribute('href') || '') + '|' + (el.textContent || '').trim().slice(0, 50) + '|' + Object.keys(el.dataset).join(',')).slice(0, 160);
            if (seen.has(key)) return; seen.add(key);
            el.setAttribute('data-audit', out.length); out.push({ i: out.length, key, text: (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 50), href: el.getAttribute('href') || '' });
          });
          return out;
        }""")

    ROLES = [('GC/CM', 'Example Builders'), ('Sub', 'Clearwater'), ('Architect', 'Example Architecture'), ('Owner', 'School District')]
    for label, role in ROLES:
        c, g, E = fresh(role)
        tabs = g.evaluate("[...document.querySelectorAll('[data-nav]')].map(a => a.dataset.nav)")
        if not tabs: issue('no tabs', label, 'the tab bar was not found')
        vlist = list(dict.fromkeys(tabs + ['change']))
        for v in vlist:
            if v == 'change':
                g.evaluate("location.hash = '#changes'"); g.wait_for_timeout(1200)
                row = g.query_selector('[data-copen]')
                if not row: issue('empty list', label + ' changes', 'no change to open'); continue
                row.click(); g.wait_for_timeout(1500)
            else:
                g.evaluate("v => location.hash = '#' + v", v); g.wait_for_timeout(1500)
            here = view(g); txt = text(g)
            st = {'party': label, 'view': here, 'clicks': 0, 'no_effect': [], 'errors': []}
            if len(txt.strip()) < 20: issue('blank screen', label + ' #' + v, repr(txt[:80]))
            if 'Loading' in txt[:200] : g.wait_for_timeout(2000);
            if not g.query_selector('[data-nav]') or not g.is_visible('[data-nav]'): issue('no way out', label + ' #' + v, 'the tab bar is hidden on this screen')
            ctl = controls(g)
            for k in ctl[:60]:
                if any(w in k['text'] for w in ('Leave the sample', 'Sign out', 'Export')): continue
                if back_to_app(g, here):
                    ctl2 = controls(g)
                close_overlays(g)
                if view(g) != here:
                    g.evaluate("v => location.hash = '#' + v", here if here != 'change' else 'change'); g.wait_for_timeout(900)
                before = g.evaluate("""() => { window.__m = 0; window.__o && window.__o.disconnect(); window.__o = new MutationObserver(l => window.__m += l.length); window.__o.observe(document.body, {subtree: true, childList: true, attributes: true, characterData: true}); return location.href; }""")
                el = g.query_selector('[data-audit="%d"]' % k['i'])
                if not el:
                    controls(g); el = g.query_selector('[data-audit="%d"]' % k['i'])
                    if not el: continue
                n0 = len(E)
                try: el.click(timeout=2000)
                except Exception as ex: issue('cannot click', label + ' #' + here, '%s (%s)' % (k['text'] or k['key'], str(ex).split('\n')[0][:120])); continue
                g.wait_for_timeout(700)
                after = g.evaluate("[location.href, window.__m, document.querySelectorAll('.modal').length, document.querySelector('#toast') ? document.querySelector('#toast').innerText : '']")
                st['clicks'] += 1
                if len(E) > n0:
                    for e in E[n0:]: issue('script error', label + ' #' + here, '%s -> %s' % (k['text'] or k['key'], e))
                if after[0] == before and after[1] == 0 and not after[2]:
                    st['no_effect'].append(k['text'] or k['key'])
                    issue('does nothing', label + ' #' + here, k['text'] or k['key'])
                # Coming back: if the click left this screen, the browser Back button should return here.
                if after[0] != before and urlparse(after[0]).path == urlparse(before).path and '#' in before:
                    g.go_back(); g.wait_for_timeout(1000)
                    if g.evaluate('location.href') != before: issue('back button', label + ' #' + here, 'after "%s", Back went to %s' % (k['text'], g.evaluate('location.hash')))
                    # Back may be fine but a screen that needs saved state (a change, a document) may come back blank.
                    if len(text(g).strip()) < 20: issue('blank after back', label + ' #' + here, k['text'])
            states.append(st)
        c.close()

    # ---------- 3. first visit, unknown address, the getting-started screen, the field page ----------
    c, g, E = fresh(start='/app/')
    if view(g) != 'start': issue('first visit', '/app/', 'a first visit did not open the getting-started screen (got #%s)' % view(g))
    g.evaluate("location.hash = '#no-such-page'"); g.wait_for_timeout(1200)
    if view(g) not in ('home', 'start'): issue('unknown address', '/app/#no-such-page', 'stayed on #' + view(g))
    for e in E: issue('script error', 'first visit', e)
    c.close()
    c, g, E = fresh(start='/app/field/')
    if len(g.inner_text('body').strip()) < 20: issue('blank screen', '/app/field/', 'nothing shown without a link token')
    if not g.query_selector('a[href]'): issue('dead end', '/app/field/', 'no link anywhere (e.g. to the site) when the link is missing or wrong')
    c.close()

    # ---------- 4. phones: can every tab be reached? ----------
    c, g, E = fresh('Example Builders', 390, 844)
    nav = g.evaluate("""() => { const t = [...document.querySelectorAll('[data-nav]')]; const vw = innerWidth;
      return t.map(a => { const r = a.getBoundingClientRect(); const s = getComputedStyle(a.parentElement); return { nav: a.dataset.nav, off: r.right > vw + 1 || r.left < -1, scroll: s.overflowX }; }); }""")
    off = [n['nav'] for n in nav if n['off']]
    if off:
        scrollable = g.evaluate("() => { const p = document.querySelector('[data-nav]').parentElement; return p.scrollWidth > p.clientWidth && /auto|scroll/.test(getComputedStyle(p).overflowX); }")
        if not scrollable: issue('phone nav', 'tab bar at 390px', 'tabs off screen and not scrollable: ' + ', '.join(off))
        else: issue('phone nav (minor)', 'tab bar at 390px', 'tabs need sideways scrolling to reach: ' + ', '.join(off))
    over = g.evaluate("document.documentElement.scrollWidth")
    if over > 392: issue('phone width', '#home at 390px', 'page is %dpx wide (scrolls sideways)' % over)
    c.close()

    # ---------- 5. keyboard: can you see where you are? ----------
    c, g, E = fresh('Example Builders')
    missing = []
    for i in range(30):
        g.keyboard.press('Tab'); g.wait_for_timeout(60)
        f = g.evaluate("""() => { const a = document.activeElement; if (!a || a === document.body) return null; const s = getComputedStyle(a);
          const vis = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || (s.boxShadow && s.boxShadow !== 'none');
          return { vis, text: (a.textContent || a.getAttribute('aria-label') || a.tagName).trim().slice(0, 40) }; }""")
        if f and not f['vis']: missing.append(f['text'])
    if missing: issue('focus not visible', 'keyboard on #home', ', '.join(dict.fromkeys(missing)))
    c.close()
    b.close()

report = {'pages': pages, 'states': states, 'external_links': sorted(external), 'issues': issues}
json.dump(report, open('tools/nav_audit_report.json', 'w'), indent=1)
print('pages: %d  app screens: %d  clicks: %d  external links (not fetched): %d' % (len(pages), len(states), sum(s['clicks'] for s in states), len(external)))
by = {}
for x in issues: by.setdefault(x['kind'], []).append(x)
for k, xs in sorted(by.items()):
    print('\n%s (%d)' % (k, len(xs)))
    for x in xs[:40]: print('  %s: %s' % (x['where'], x['detail']))
