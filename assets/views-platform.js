/* The platform's screens: Home (W1), Changes and the change thread (W2), Record (W5), Contracts (W3), Schedule and delay (W4),
   Activity (W6), the AI step detail (W7), Project settings and the field link (W8).
   Data and visibility come from assets/platform.js; the money checks from checks.js; schedules and delay from views-time.js. */
(function () {
  'use strict';
  var A = window.CSApp, P = window.CSPlat, R = window.CSRules, esc = A.esc, store = A.store, app = A.app, M = A.M;
  var V = window.CSViews = window.CSViews || {};
  var q = P.q;
  var STATUS = { draft: 'Draft', with_gc: 'With GC/CM', with_architect: 'With architect', with_owner: 'With owner', returned: 'Returned', bundled: 'In a proposal', approved: 'Approved', rejected: 'Rejected', withdrawn: 'Withdrawn' };
  var OPEN = { draft: 1, with_gc: 1, with_architect: 1, with_owner: 1, returned: 1 };
  var REASONS = [['missing_backup', 'Backup missing or unclear'], ['markup_over_limit', 'Markup over the contract limit'], ['fee_on_excluded', 'Fee on excluded items'],
    ['late_notice', 'Notice given late'], ['quantities_unclear', 'Quantities or rates unclear'], ['not_a_change', 'Work is already in the contract'],
    ['needs_time_analysis', 'Time claim needs schedule analysis'], ['wrong_party', 'Wrong party is paying'], ['other', 'Other']];
  var REASON = {}; REASONS.forEach(function (r) { REASON[r[0]] = r[1]; });
  var KIND = { note: 'Note', draft: 'Draft', confirm: 'Numbers confirmed', check: 'Checks run', explain: 'Finding explained', submit: 'Sent', forward: 'Forwarded', return: 'Returned',
    approve: 'Approved', reject: 'Rejected', comment: 'Comment', bundle: 'Put in a proposal', notice: 'Notice', schedule: 'Delay analyzed', link: 'Linked' };
  var DOCKIND = { rfi: 'RFI', asi: 'ASI', submittal: 'Submittal', daily_report: 'Daily report', minutes: 'Approved minutes', contract: 'Contract', spec: 'Spec section', change_order: 'Change order', notice: 'Notice', schedule: 'Schedule', other: 'Other' };
  var TERM = { notice_days: 'Notice window (days)', notice_days_by_cause: 'Notice window by cause (days)', notice_flowdown: 'Prime notice terms flow down', markup_own: 'Markup on own work', markup_lower_tier: 'Markup on lower tiers',
    markup_own_pct: 'Sub markup on own work (%)', markup_lower_pct: 'Sub markup on lower tiers (%)', markup_total_pct: 'Total markup cap (%)', fee_pct: 'CM fee on changes (%)', fee_allowed_on: 'Fee allowed on', pricing_days: 'Days to price a change',
    pay_if_paid: 'Pay-if-paid', delay_compensable: 'Delay: who pays', labor_burden_pct: 'Labor burden (%)', blue_book_pct: 'Owned equipment (% of Blue Book)', approval_limit: 'Owner’s rep approval limit ($)',
    contract_days: 'Contract time (days)', liquidated_damages_per_day: 'Liquidated damages ($/day)', daily_delay_rate: 'Delay rate, general conditions ($/day)', sgc_total: 'General conditions total ($)',
    extension_requires_critical_path: 'Extension needs critical-path delay', compensable_causes: 'Paid delay causes', concurrent_delay: 'Concurrent delay', cp_days: 'Days to submit a proposal after notice', review_days: 'Days to respond to a proposal', rfi_days: 'Days to answer an RFI' };

  function ctx() { return P.ctx(); }
  function me() { return ctx().viewAs; }
  function role() { return P.myRole(); }
  function name(id) { return P.coName(id); }
  function fail(e) { A.toast((e && e.message) || String(e)); }
  function when(d) { if (!d) return '—'; var t = new Date(d); return t.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ', ' + t.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }); }
  function day(iso) { if (!iso) return '—'; var x = new Date(String(iso).slice(0, 10) + 'T00:00:00Z'); return x.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }); }
  function today() { return new Date().toISOString().slice(0, 10); }
  function money(x) { return x == null ? '—' : M(+x); }
  function sheet(no, title, body) {
    return '<div class="wrap"><div class="ph1"><div><span class="eyebrow">' + esc(no) + (ctx() ? ' · ' + esc(ctx().project.name) : '') + '</span><h1 style="margin-top:8px">' + esc(title) + '</h1></div></div>' + body + '</div>';
  }
  // Markup colors: green = approved, red = a problem, amber = your turn. (Blue is kept for what the AI wrote.)
  function badge(status, c) {
    var turn = c && OPEN[status] && c.holder && ctx() && c.holder === ctx().viewAs;
    return '<span class="badge' + (status === 'approved' ? ' ok' : status === 'returned' || status === 'rejected' ? ' fail' : turn ? ' turn' : '') + '">' + esc(STATUS[status] || status) + (turn ? ' · your turn' : '') + '</span>';
  }
  function primeTerm(key) { return P.term(P.prime(), key); }
  function primeClause(key) { var k = P.prime(), t = k && k.terms[key]; return t ? t.clause : ''; }

  /* ---------- getting in: connect, sign in, pick a project ---------- */
  function gate(render) {
    app.innerHTML = '<div class="wrap"><div class="reading"><div class="spinner"></div><h2>' + (P.isSample() ? 'Opening the sample project…' : 'Opening ClauseStream…') + '</h2></div></div>';
    P.connect().then(function () {
      var cfg = P.cfg();
      if (!cfg || !cfg.configured) return app.innerHTML = sheet('Home', 'ClauseStream', '<div class="banner warn"><span>Live projects need the project database, which this copy of the site isn’t connected to. <button class="link" data-entersample="1">Open the sample project</button> instead, or use the <a class="link" href="#upload">quick check</a>.</span></div>');
      if (!P.user()) return signIn();
      if (!ctx()) return V.project();
      render(ctx());
    }).catch(fail);
  }
  function signIn(sent) {
    app.innerHTML = sheet('Sign in', 'Sign in to your projects', '<div class="card sec" style="max-width:520px">' +
      (sent ? '<p style="margin:0 0 6px"><b>Check your email.</b> We sent a sign-in link to ' + esc(sent) + '. Open it in this browser.</p><p class="fine" style="margin:0">No password. The link works once and expires after an hour.</p>'
        : '<p style="margin:0 0 14px;color:var(--muted)">Each company on a project (sub, GC/CM, architect, owner) works from the same record, and sees what its contracts allow. Sign in with your email; we send a one-time link.</p>' +
          '<form id="signin" class="grid" style="grid-template-columns:minmax(0,1fr) auto;gap:10px"><div class="inp"><input type="email" id="email" required placeholder="you@company.com" autocomplete="email"></div><button class="btn primary" type="submit">Email me a link</button></form>') + '</div>' +
      '<div class="card sec" style="max-width:520px;margin-top:16px"><div class="sec-h"><h3>Just looking?</h3><span class="tagr none">no sign-in</span></div><p style="margin:0 0 12px;color:var(--muted)">Open the sample project: a synthetic school modernization with its record, contracts, subs and changes. It runs in this browser only and nothing is saved.</p><button class="btn" data-entersample="1">Open the sample project</button> <a class="btn ghost" href="#upload">Quick check a proposal</a></div>');
    var f = document.getElementById('signin');
    if (f) f.addEventListener('submit', function (e) {
      e.preventDefault(); var email = document.getElementById('email').value.trim();
      q(P.sb().auth.signInWithOtp({ email: email, options: { emailRedirectTo: location.origin + '/app/?signin=1' } })).then(function () { signIn(email); }).catch(fail);
    });
  }

  /* ---------- loading what the viewer may see ---------- */
  function loadChanges() {
    return q(P.sb().from('changes').select('*').eq('project_id', ctx().project.id).order('number')).then(function (rows) { return rows.filter(P.sees.change); });
  }
  function loadEvents(changeIds) {
    var Q = P.sb().from('events').select('*').eq('project_id', ctx().project.id);
    if (changeIds) Q = Q.in('change_id', changeIds);
    return q(Q.order('id'));
  }
  var people = {};
  function loadPeople() { return q(P.sb().rpc('project_people', { p: ctx().project.id })).then(function (rows) { people = {}; rows.forEach(function (r) { people[r.user_id] = r; }); return rows; }).catch(function () { return []; }); }

  // What the viewer should do next on a change, or null.
  function nextStep(c) {
    var v = me(), r = role();
    if (!OPEN[c.status]) return null;
    if (c.tier === 'sub_request') {
      if (c.from_company === v && (c.status === 'draft' || c.status === 'returned')) return c.status === 'returned' ? 'Fix and resend' : 'Send to the GC/CM';
      if (c.to_company === v && c.status === 'with_gc') return 'Put in a proposal, or return';
      return null;
    }
    if (c.from_company === v && (c.status === 'draft' || c.status === 'returned')) return c.status === 'returned' ? 'Fix the findings and resend' : 'Draft, check and send';
    if (c.holder === v && c.status === 'with_architect' && r === 'architect') return 'Review: forward or return';
    if (c.holder === v && c.status === 'with_owner' && r === 'owner') return 'Decide: approve, reject or return';
    return null;
  }

  /* ---------- clocks: from the contracts' own terms ---------- */
  function noticeDays(c) {
    var by = primeTerm('notice_days_by_cause'), type = (c.cause || {}).type;
    if (c.tier === 'sub_request') { var k = ctx().contracts[c.contract_id]; var n = P.term(k, 'notice_days'); if (n != null) return { days: +n, clause: k.terms.notice_days.clause + ' (subcontract)' }; }
    if (by && typeof by === 'object') return { days: by[type] != null ? +by[type] : +by['Other event'] || 7, clause: primeClause('notice_days_by_cause') };
    return null;
  }
  function clocks(c, evs) {
    var out = [], mine = evs.filter(function (e) { return e.change_id === c.id; });
    var ev = (c.cause || {}).event_date, nd = noticeDays(c), noticed = (c.meta || {}).notice_date || (mine.filter(function (e) { return e.kind === 'notice'; })[0] || {}).created_at;
    if (ev && nd) {
      var due = R.addDays(ev, nd.days);
      if (noticed) { var late = R.daysBetween(due, String(noticed).slice(0, 10)); out.push({ what: 'Notice', text: 'given ' + day(noticed) + (late > 0 ? ', ' + late + ' days late' : ', on time') + ' (due ' + day(due) + ')', clause: nd.clause, bad: late > 0 }); }
      else out.push({ what: 'Notice', text: 'due ' + day(due), clause: nd.clause, due: due, bad: due < today() });
    }
    if (c.tier === 'proposal' && noticed && (c.status === 'draft' || c.status === 'returned')) {
      var cpd = primeTerm('cp_days'); if (cpd) out.push({ what: 'Proposal', text: 'due ' + day(R.addDays(String(noticed).slice(0, 10), +cpd)), clause: primeClause('cp_days'), due: R.addDays(String(noticed).slice(0, 10), +cpd) });
    }
    var sent = mine.filter(function (e) { return e.kind === 'submit'; }).slice(-1)[0];
    if (c.tier === 'proposal' && sent && (c.status === 'with_architect' || c.status === 'with_owner')) {
      var rd = primeTerm('review_days');
      if (rd) { var start = String(sent.created_at).slice(0, 10), waited = R.daysBetween(start, today()), dueR = R.addDays(start, +rd);
        out.push({ what: 'Review', text: 'day ' + waited + ' of ' + rd + (waited > rd ? ', ' + (waited - rd) + ' days overdue' : ''), clause: primeClause('review_days'), due: dueR, bad: waited > rd, waited: waited }); }
    }
    out.forEach(function (k) { if (!k.bad && k.due) { var left = R.daysBetween(today(), k.due); if (left >= 0 && left <= 3) k.soon = true; } });
    return out;
  }

  // Field photos: in the sample they're kept in this tab only; live, they're signed links to private storage.
  var signed = {};
  function photos(s) {
    if (!s.photos || !s.photos.length) return '';
    return '<div class="fphotos">' + s.photos.map(function (ph) {
      var src = /^blob:/.test(ph) ? ph : signed[ph];
      if (!src && P.sb().storage) P.sb().storage.from('documents').createSignedUrl(ph, 3600).then(function (r) { if (r.data) { signed[ph] = r.data.signedUrl; var im = document.querySelector('img[data-ph="' + ph + '"]'); if (im) im.src = r.data.signedUrl; } });
      return '<img data-ph="' + esc(ph) + '" alt="Photo from the field" src="' + esc(src || '') + '">';
    }).join('') + '</div>';
  }
  /* ---------- W1 Home ---------- */
  V.home = function () {
    gate(function (C) {
      var pid = C.project.id;
      Promise.all([loadChanges(), loadEvents(), q(P.sb().from('field_submissions').select('*').eq('project_id', pid).eq('status', 'unverified')).catch(function () { return []; }), loadSov()]).then(function (r) {
        var ch = r[0], evs = r[1], subs = r[2].filter(function (s) { return s.company_id === me(); }), byId = {}; ch.forEach(function (c) { byId[c.id] = c; });
        evs = evs.filter(function (e) { return P.sees.event(e, byId); });
        var todo = ch.map(function (c) { return { c: c, step: nextStep(c) }; }).filter(function (x) { return x.step; });
        var dl = []; ch.forEach(function (c) { if (!OPEN[c.status]) return; clocks(c, evs).forEach(function (k) { if (k.due && !(k.what === 'Notice' && !k.bad && k.text.indexOf('given') === 0)) dl.push({ c: c, k: k }); }); });
        dl.sort(function (a, b) { return a.k.due < b.k.due ? -1 : 1; });
        var open = ch.filter(function (c) { return OPEN[c.status]; }), rate = costPerDay(r[3]);
        var sum = function (list) { return list.reduce(function (s, c) { return s + (+c.amount || 0); }, 0); };
        var pend = open.filter(function (c) { return c.tier === (role() === 'sub' ? 'sub_request' : 'proposal'); }), appr = ch.filter(function (c) { return c.status === 'approved' && c.tier === (role() === 'sub' ? 'sub_request' : 'proposal'); });
        var ret = ch.filter(function (c) { return c.status === 'returned'; }), days = open.filter(function (c) { return c.tier === 'proposal'; }).reduce(function (s, c) { return s + (+c.days || 0); }, 0);
        var waitRows = todo.map(function (x) { return '<tr data-copen="' + x.c.id + '"><td><span class="t">' + esc(x.c.title) + '</span><span class="id">' + esc(x.c.number) + ' · ' + (x.c.tier === 'sub_request' ? 'Sub request from ' + esc(name(x.c.from_company)) : 'Proposal') + '</span></td><td>' + badge(x.c.status) + '</td><td><b>' + esc(x.step) + '</b></td></tr>'; }).join('');
        var fieldRows = subs.map(function (s) { return '<li class="info"><span class="qd"></span><div><b>From the field' + (s.sender_name ? ', ' + esc(s.sender_name) : '') + '</b> <span class="fine">' + when(s.created_at) + ' · unverified</span><p style="margin:4px 0 8px">' + esc(s.body) + '</p><button class="btn sm" data-fconfirm="' + s.id + '">Make it a change request</button> <button class="btn ghost sm" data-fdiscard="' + s.id + '">Discard</button></div></li>'; }).join('');
        var body = '<p style="margin:-6px 0 18px;color:var(--muted)">Viewing as <b>' + esc(name(me())) + '</b> (' + esc(P.ROLE[role()]) + '). ' + todo.length + ' waiting on you.' + (P.isSample() ? ' Switch who you’re viewing as in the band above to see what each party sees.' : '') + '</p>' +
          '<div class="cols" style="--cols:minmax(0,1.5fr) minmax(0,1fr)"><div>' +
          (fieldRows ? '<div class="card sec" style="margin-bottom:16px"><div class="sec-h"><h3>From your field link (' + subs.length + ')</h3><span class="tagr chk">unverified</span></div><ul class="qual">' + fieldRows + '</ul><p class="fine" style="margin:8px 0 0">Nothing from the field reaches the GC/CM until you confirm it.</p></div>' : '') +
          '<div class="card tbl-wrap">' + (todo.length ? '<table class="tbl turn"><thead><tr><th>Waiting on you</th><th>Status</th><th>Next</th></tr></thead><tbody>' + waitRows + '</tbody></table>' : '<p style="padding:18px;margin:0">Nothing is waiting on you. <a class="link" href="#changes">See all changes</a></p>') + '</div></div>' +
          '<div><div class="card sec"><div class="sec-h"><h3>Clocks</h3><span class="fine">from the contracts</span></div>' + (dl.length ? '<ul class="clocks">' + dl.slice(0, 7).map(function (x) { return '<li class="' + (x.k.bad ? 'bad' : '') + '"><button class="link" data-copen="' + x.c.id + '">' + esc(x.c.number) + '</button> ' + esc(x.k.what) + ' ' + esc(x.k.text) + ' <span class="fine">' + esc(x.k.clause) + '</span></li>'; }).join('') + '</ul>' : '<p class="fine" style="margin:0">No open clocks.</p>') + '</div>' +
          '<div class="card sec" style="margin-top:16px"><div class="sec-h"><h3>Money</h3></div><div class="tblock"><div><span>Pending</span><b>' + money(sum(pend)) + '</b></div><div><span>Approved</span><b>' + money(sum(appr)) + '</b></div><div><span>Returned</span><b>' + ret.length + '</b></div>' +
          (role() !== 'sub' && rate.value ? '<div><span>Delay exposure</span><b>' + days + ' days × ' + money(rate.value) + '</b></div>' : '') + '</div>' + (role() !== 'sub' && rate.value ? '<p class="fine" style="margin:8px 0 0">Days claimed on open proposals, at ' + esc(rate.label) + '. Not a finding: each claim still needs its schedule analysis.</p>' : '') + '</div>' +
          '<div class="card sec" style="margin-top:16px"><div class="sec-h"><h3>Check before you send</h3></div><p class="fine" style="margin:0 0 10px">No project? The quick check reads one proposal against a contract and marks what would get it sent back.</p><a class="btn sm" href="#upload">Quick check a proposal</a></div></div></div>';
        app.innerHTML = sheet('Home', 'Waiting on you', body);
      }).catch(fail);
    });
  };

  /* ---------- 01 Changes ---------- */
  V.changes = function () {
    gate(function (C) {
      loadChanges().then(function (ch) {
        var filt = store('cs_chfilter') || 'all', rows = ch.filter(function (c) { return filt === 'mine' ? !!nextStep(c) : filt === 'open' ? OPEN[c.status] : true; });
        var tr = rows.map(function (c) {
          return '<tr data-copen="' + c.id + '"><td><span class="t">' + esc(c.title) + '</span><span class="id">' + esc(c.number) + ' · ' + (c.tier === 'sub_request' ? 'Sub request' : 'Proposal') + '</span></td><td>' + esc(name(c.from_company)) + '</td><td>' + badge(c.status, c) + '</td><td>' + (OPEN[c.status] && c.holder ? esc(name(c.holder)) : '—') + '</td><td class="r">' + money(c.amount) + '</td><td class="r">' + (c.days ? c.days + ' d' : '—') + '</td></tr>';
        }).join('');
        var canRaise = role() === 'sub' || role() === 'gc';
        app.innerHTML = sheet('01 Changes', 'Changes', '<div class="pills" style="margin:-6px 0 14px">' + [['all', 'All you can see (' + ch.length + ')'], ['open', 'Open'], ['mine', 'Waiting on you']].map(function (f) { return '<button class="pill" data-chf="' + f[0] + '" aria-pressed="' + (filt === f[0]) + '">' + f[1] + '</button>'; }).join('') + '</div>' +
          '<div class="cols" style="--cols:minmax(0,1.7fr) minmax(0,1fr)"><div class="card tbl-wrap">' + (rows.length ? '<table class="tbl"><thead><tr><th>Change</th><th>From</th><th>Status</th><th>With</th><th class="r">Amount</th><th class="r">Days</th></tr></thead><tbody>' + tr + '</tbody></table>' : '<p style="padding:18px;margin:0">None here.</p>') + '</div>' +
          '<div class="card sec"><div class="sec-h"><h3>Raise a change</h3></div>' + (canRaise ? '<p class="fine" style="margin:0 0 10px">' + (role() === 'sub' ? 'A change request to the GC/CM, under your subcontract.' : 'A change proposal to the owner, under the prime contract.') + ' Write it the way you’d say it on site.</p><form id="newc"><div class="fd"><label><span>Short title</span></label><div class="inp"><input id="ctitle" required placeholder="e.g. Extra drains at gym roof"></div></div>' +
            '<div class="fd" style="margin-top:10px"><label><span>What happened</span></label><div class="inp" style="height:auto"><textarea id="cnote" rows="4" required placeholder="e.g. RFI-112 answer adds two roof drains at the gym. We need to tie into the existing leader and cut the deck."></textarea></div></div>' +
            '<div class="grid" style="margin-top:10px"><div class="fd"><label><span>What caused it</span></label><div class="inp sel"><select id="ccause">' + ['RFI response', 'ASI', 'Submittal return', 'Owner direction', 'Architect direction', 'Concealed condition', 'Other event'].map(function (x) { return '<option>' + x + '</option>'; }).join('') + '</select></div></div>' +
            '<div class="fd"><label><span>When</span></label><div class="inp"><input id="cdate" type="date" value="' + today() + '"></div></div></div>' +
            '<button class="btn primary" type="submit" style="margin-top:12px">Raise it</button></form><p class="fine" style="margin:10px 0 0">The notice clock starts from the date it happened.</p>'
            : '<p class="fine" style="margin:0">Changes are raised by the subs and the GC/CM. You see proposals once the GC/CM sends them.</p>') + '</div></div>');
        var f = document.getElementById('newc');
        if (f) f.addEventListener('submit', function (e) { e.preventDefault(); raise(ch); });
      }).catch(fail);
    });
  };
  function raise(ch) {
    var v = me(), r = role(), C = ctx(), pid = C.project.id, sub = r === 'sub';
    var k = sub ? P.subcontractOf(v) : P.prime(), to = sub ? (k ? k.up_company : P.byRole('gc')[0]) : (P.byRole('owner')[0]);
    if (!to) return A.toast(sub ? 'Your subcontract isn’t set up on this project yet.' : 'Add the owner to the project first.');
    var pre = sub ? 'CR-' : 'CP-', n = ch.reduce(function (m, c) { var x = parseInt(String(c.number).replace(/\D/g, ''), 10); return String(c.number).indexOf(pre) === 0 && isFinite(x) && x > m ? x : m; }, sub ? 100 : 600) + 1;
    var row = { project_id: pid, number: pre + ('0000' + n).slice(-4), title: document.getElementById('ctitle').value.trim(), tier: sub ? 'sub_request' : 'proposal', contract_id: k ? k.id : null, from_company: v, to_company: to,
      cause: { type: document.getElementById('ccause').value, event_date: document.getElementById('cdate').value || today() }, meta: { raised_in_app: true } };
    q(P.sb().from('changes').insert(row).select().single()).then(function (c) {
      return q(P.sb().from('events').insert({ project_id: pid, change_id: c.id, company_id: v, kind: 'note', body: document.getElementById('cnote').value.trim() })).then(function () { store('cs_change', c.id); A.go('change'); });
    }).catch(fail);
  }

  /* ---------- W2 the change thread ---------- */
  var caseIndex = null;
  function findCase(number) {
    if (!caseIndex) caseIndex = Promise.all(['/demo3/data/cases.json', '/demo4/data/cases.json'].map(function (u) { return fetch(u).then(function (r) { return r.ok ? r.json() : { cases: [] }; }).catch(function () { return { cases: [] }; }); }))
      .then(function (r) { var o = {}; r.forEach(function (j) { (j.cases || []).forEach(function (c) { o[c.id] = c; }); }); return o; });
    return caseIndex.then(function (o) { return o[number] || null; });
  }
  var T = null; // the change on screen: { c, evs, kids, parent, cs (case), trail }
  V.change = function () {
    gate(function (C) {
      var id = store('cs_change'); if (!id) return A.go('changes');
      var sb = P.sb();
      q(sb.from('changes').select('*').eq('id', id).maybeSingle()).then(function (c) {
        if (!c || !P.sees.change(c)) { store('cs_change', null); app.innerHTML = sheet('01 Changes', 'Not visible', '<div class="banner warn"><span>' + esc(name(me())) + ' can’t see this change under its contracts. <a class="link" href="#changes">Back to changes</a></span></div>'); return; }
        return Promise.all([loadEvents([c.id]), q(sb.from('changes').select('*').eq('project_id', C.project.id)), findCase((c.meta || {}).case_id || c.number), trail(c), loadPeople(), loadSov()]).then(function (r) {
          var all = r[1], byId = {}; all.forEach(function (x) { byId[x.id] = x; });
          T = { c: c, evs: r[0], kids: all.filter(function (x) { return x.parent_id === c.id && P.sees.change(x); }), waiting: all.filter(function (x) { return x.tier === 'sub_request' && x.status === 'with_gc' && (x.meta || {}).for_change === c.number && P.sees.change(x); }),
            parent: c.parent_id && byId[c.parent_id] && P.sees.change(byId[c.parent_id]) ? byId[c.parent_id] : null, cs: r[2], trail: r[3], rate: costPerDay(r[5]) };
          drawThread();
        });
      }).catch(fail);
    });
  };
  function stagesFor(c) {
    var e = T.evs, has = function (k) { return e.some(function (x) { return x.kind === k; }); };
    if (c.tier === 'sub_request') return [['Raised', true], ['Sent to the GC/CM', c.status !== 'draft'], ['In a proposal', !!c.parent_id || c.status === 'bundled' || c.status === 'approved' || c.status === 'rejected'], ['Decided', c.status === 'approved' || c.status === 'rejected']];
    var noticed = !!(c.meta || {}).notice_date || has('notice');
    return [['Raised', true], ['Notice', noticed], ['Sub pricing', T.kids.length > 0 || !T.waiting.length && has('confirm')], ['Proposal', has('submit')], ['Architect review', c.status === 'with_owner' || c.status === 'approved' || c.status === 'rejected'],
      ['Owner decision', c.status === 'approved' || c.status === 'rejected'], ['Executed', c.status === 'approved']];
  }
  function drawThread() {
    var c = T.c, v = me(), r = role(), evs = T.evs;
    var st = stagesFor(c), now = st.findIndex(function (s) { return !s[1]; });
    var rail = '<ol class="stages">' + st.map(function (s, i) { return '<li class="' + (s[1] ? 'done' : i === now ? 'now' : 'todo') + '"><span class="dot"></span>' + esc(s[0]) + '</li>'; }).join('') + '</ol>';
    var cl = clocks(c, evs).map(function (k) { return '<span class="clock' + (k.bad ? ' bad' : k.soon ? ' soon' : '') + '">' + esc(k.what) + ' ' + esc(k.text) + ' <span class="fine">' + esc(k.clause) + '</span></span>'; }).join('');
    var head = '<div class="thead"><div>' + badge(c.status, c) + (OPEN[c.status] && c.holder ? ' <span class="fine">with ' + esc(name(c.holder)) + '</span>' : '') + '</div><div class="fine">' + (c.tier === 'sub_request' ? 'Sub request from ' + esc(name(c.from_company)) + ' to ' + esc(name(c.to_company)) : 'Proposal from ' + esc(name(c.from_company)) + ' to ' + esc(name(c.to_company))) + ' · ' + money(c.amount) + (c.days ? ' · ' + c.days + ' days claimed' : '') + '</div>' + (cl ? '<div class="clocks-row">' + cl + '</div>' : '') + '</div>';
    var body = head + '<div class="tgrid"><div class="card sec">' + rail + '</div><div>' + stepPanel() + timePanel() + '<div class="card sec" style="margin-top:16px"><div class="sec-h"><h3>Activity on this change</h3><span class="fine">permanent</span></div>' + eventsHtml(evs) + '</div></div>' +
      '<div><div id="tlinked">' + linkedPanel() + '</div><div class="card sec" id="tevidence" style="margin-top:16px"><div class="sec-h"><h3>Evidence, cited</h3></div>' + trailHtml(T.trail) + '</div></div></div>';
    document.body.dataset.change = c.number; // the guide reads which change is on screen
    app.innerHTML = sheet('01 Changes · ' + c.number, c.title, body);
  }
  function linkedPanel() {
    var c = T.c, r = role();
    if (c.tier === 'sub_request') return '<div class="card sec"><div class="sec-h"><h3>Under</h3></div><p style="margin:0">' + esc((ctx().contracts[c.contract_id] || {}).title || 'Subcontract') + '</p>' + photos({ photos: (c.meta || {}).photos }) + (T.parent ? '<p class="fine" style="margin:8px 0 0">In <button class="link" data-copen="' + T.parent.id + '">' + esc(T.parent.number) + '</button></p>' : '') +
      ((c.meta || {}).lines && c.meta.lines.length ? '<table class="tbl" style="margin-top:10px"><tbody>' + c.meta.lines.map(function (l) { return '<tr><td>' + esc(l.desc) + '</td><td class="r">' + money(l.amount) + '</td></tr>'; }).join('') + '</tbody></table>' : '') +
      (function () { var f = subFlags(c); return f.length ? '<div class="sec-h" style="margin-top:14px"><h3>Checks on this request</h3><span class="fine">code</span></div><ul class="plain">' + f.map(function (x) { return '<li class="flagline">' + esc(x) + '</li>'; }).join('') + '</ul>' : (c.meta || {}).lines && c.meta.lines.length ? '<p class="fine" style="margin:10px 0 0">Lines add up, and markups are within the subcontract and the prime contract.</p>' : ''; })() + '</div>';
    var reqs = (c.meta || {}).requests || [];
    var visible = T.kids.map(function (k) { return '<li><button class="link" data-copen="' + k.id + '">' + esc(k.number) + '</button> ' + esc(name(k.from_company)) + ' <b>' + money(k.amount) + '</b> ' + badge(k.status, k) + '</li>'; }).join('');
    var summary = !visible && reqs.length ? reqs.map(function (x) { return '<li>' + esc(x.number) + ' ' + esc(x.company) + ' <b>' + money(x.amount) + '</b></li>'; }).join('') : '';
    return '<div class="card sec"><div class="sec-h"><h3>Sub requests in it</h3></div>' + (visible || summary ? '<ul class="plain">' + (visible || summary) + '</ul>' + (summary ? '<p class="fine" style="margin:8px 0 0">Numbers and amounts as the GC/CM listed them. The subs’ own lines stay between each sub and the GC/CM.</p>' : '') : '<p class="fine" style="margin:0">None yet.</p>') + '</div>';
  }
  // Code checks on a sub's request: the lines add up, and each markup is within the subcontract and the prime contract.
  function subFlags(c) {
    var out = [], ls = (c.meta || {}).lines || [], k = ctx().contracts[c.contract_id], prime = P.prime();
    if (ls.length) { var t = ls.reduce(function (s, l) { return s + (+l.amount || 0); }, 0); if (Math.abs(t - (+c.amount || 0)) > 0.5) out.push('The lines add to ' + money(t) + ' but the total reads ' + money(c.amount) + '.'); }
    ls.forEach(function (l) {
      var m = String(l.desc).match(/(\d+(?:\.\d+)?)\s*%/); if (!m || !/oh&p|markup|overhead|profit/i.test(l.desc)) return;
      var pct = +m[1], lower = /lower|tier|sub-?sub/i.test(l.desc);
      var subLim = P.term(k, lower ? 'markup_lower_tier' : 'markup_own'), primeLim = P.term(prime, lower ? 'markup_lower_pct' : 'markup_own_pct');
      if (subLim != null && pct > +subLim) out.push(l.desc + ': over the subcontract’s ' + subLim + '% (' + ((k.terms[lower ? 'markup_lower_tier' : 'markup_own'] || {}).clause || '') + ').');
      if (primeLim != null && pct > +primeLim) out.push(l.desc + ': over the prime contract’s ' + primeLim + '% (' + primeClause(lower ? 'markup_lower_pct' : 'markup_own_pct') + '), so the GC/CM can’t pass it to the owner as priced.');
    });
    return out;
  }
  function stepItem(done, label, action, note) { return '<li class="' + (done ? 'done' : '') + '"><span class="chk">' + (done ? '✓' : '') + '</span><div><b>' + label + '</b>' + (note ? '<p class="fine" style="margin:2px 0 0">' + note + '</p>' : '') + (action ? '<div style="margin-top:6px">' + action + '</div>' : '') + '</div></li>'; }
  function stepPanel() {
    var c = T.c, v = me(), r = role(), e = T.evs, has = function (k) { return e.some(function (x) { return x.kind === k; }); };
    var reasonSel = '<div class="fd" id="reasonbox" hidden style="margin-top:10px"><label><span>Why it’s going back</span></label><div class="inp sel"><select id="treason">' + REASONS.map(function (x) { return '<option value="' + x[0] + '">' + x[1] + '</option>'; }).join('') + '</select></div></div>';
    var note = '<div class="fd" style="margin-top:12px"><label><span>Note (goes in the activity log)</span></label><div class="inp" style="height:auto"><textarea id="tbody" rows="3"></textarea></div></div>';
    var comment = '<div class="acts" style="margin-top:10px"><button class="btn ghost sm" data-tact="comment">Add comment</button></div>';
    if (!OPEN[c.status]) return '<div class="card sec"><p style="margin:0">This change is ' + esc(STATUS[c.status].toLowerCase()) + '.</p>' + note + comment + '</div>';
    if (c.tier === 'sub_request') {
      if (c.from_company === v && (c.status === 'draft' || c.status === 'returned'))
        return '<div class="card sec"><div class="sec-h"><h3>Your step: send it</h3></div><p class="fine" style="margin:0 0 10px">Amount ' + money(c.amount) + '. The GC/CM sees it once sent; until then only ' + esc(name(v)) + ' can.</p>' + amountEdit() + note + '<div class="acts" style="margin-top:10px"><button class="btn primary" data-tact="submit">Send to ' + esc(name(c.to_company)) + '</button></div></div>';
      if (c.to_company === v && c.status === 'with_gc') {
        var target = (c.meta || {}).for_change;
        return '<div class="card sec"><div class="sec-h"><h3>Your step: put it in a proposal, or return it</h3></div>' + (target ? '<p class="fine" style="margin:0 0 10px">The sub says it belongs to ' + esc(target) + '.</p>' : '') + '<div class="acts"><button class="btn primary" data-tbundle="' + esc(target || '') + '">Put it in ' + esc(target || 'a proposal') + '</button><button class="btn" data-tact="return">Return to ' + esc(name(c.from_company)) + '</button></div>' + reasonSel + note + '</div>';
      }
      return '<div class="card sec"><p style="margin:0;color:var(--muted)">With ' + esc(name(c.holder)) + '.</p>' + note + comment + '</div>';
    }
    if (c.from_company === v && (c.status === 'draft' || c.status === 'returned')) {
      var lastDraft = 0; e.forEach(function (x) { if (x.kind === 'draft' || x.kind === 'confirm') lastDraft = x.id; });
      var drafted = e.some(function (x) { return x.kind === 'draft'; }), confirmed = e.some(function (x) { return x.kind === 'confirm'; });
      var lastCheck = e.filter(function (x) { return x.kind === 'check' && x.id > lastDraft; }).slice(-1)[0], findings = lastCheck ? +((lastCheck.payload || {}).findings || 0) : null;
      var explained = lastCheck && e.some(function (x) { return x.kind === 'explain' && x.id > lastCheck.id; });
      var block = R.sendBlocker(c, e), noticed = !!(c.meta || {}).notice_date || has('notice');
      var waiting = T.waiting.length;
      var steps = '<ol class="steps">' +
        stepItem(noticed, 'Notice', noticed ? null : '<button class="btn sm" data-tnotice="1">Draft the notice</button>', noticed ? 'Given ' + day((c.meta || {}).notice_date || (e.filter(function (x) { return x.kind === 'notice'; })[0] || {}).created_at) + '.' : 'Drafted by code from the prime contract’s notice clause.') +
        stepItem(waiting === 0, 'Sub pricing', waiting ? '<button class="btn sm" data-tbundleall="1">Put the ' + waiting + ' waiting request' + (waiting === 1 ? '' : 's') + ' in</button>' : null, (T.kids.length ? T.kids.length + ' sub request' + (T.kids.length === 1 ? '' : 's') + ' in this proposal.' : waiting ? waiting + ' waiting from the subs.' : 'No sub requests.') + rollup().map(function (x) { return '<span class="flag">' + esc(x) + '</span>'; }).join('')) +
        stepItem(drafted, 'Draft from the record', '<button class="btn sm" data-tdraft="1">' + (drafted ? 'Draft again' : 'Draft it') + '</button>', 'The AI may only cite entries in the record; you accept, edit or reject it.') +
        stepItem(confirmed && lastDraft && e.filter(function (x) { return x.kind === 'confirm'; }).slice(-1)[0].id >= lastDraft, 'Confirm the numbers', '<button class="btn sm" data-tconfirm="1">Review and confirm</button>', T.cs ? 'From the priced cover sheet: ' + money((T.cs.cover_sheet || {}).total_requested) + '.' : 'Amount ' + money(c.amount) + '.') +
        stepItem(!!lastCheck, 'Run the contract checks', '<button class="btn sm" data-tcheck="1">' + (lastCheck ? 'Run again' : 'Run the checks') + '</button>', lastCheck ? (findings ? findings + ' finding' + (findings === 1 ? '' : 's') + ' to fix or explain.' : 'Nothing to fix.') : 'Computed by code against the prime contract.') +
        (findings ? stepItem(explained, 'Fix or explain each finding', explained ? null : '<div class="inp" style="height:auto"><textarea id="texplain" rows="2" placeholder="What you changed, or why it stands"></textarea></div><button class="btn sm" data-texplain="1" style="margin-top:6px">Save the explanation</button>', lastCheck ? '<pre class="checkout">' + esc(lastCheck.body || '') + '</pre>' : '') : '') +
        '</ol>';
      return '<div class="card sec"><div class="sec-h"><h3>Your step: the proposal</h3><span class="fine">in order</span></div>' + steps + note +
        '<div class="acts" style="margin-top:12px"><button class="btn primary" data-tact="submit"' + (block ? ' disabled title="' + esc(block) + '"' : '') + '>Send to ' + esc(name(P.byRole('architect')[0] || c.to_company)) + '</button>' + (block ? '<span class="fine">' + esc(block) + '</span>' : '') + '</div></div>';
    }
    if (c.holder === v && c.status === 'with_architect' && r === 'architect')
      return '<div class="card sec"><div class="sec-h"><h3>Your step: review</h3></div><p class="fine" style="margin:0 0 10px">The checks and the evidence below are what the GC/CM sent. Forward it to the owner with your recommendation, or return it with a reason.</p><div class="acts"><button class="btn primary" data-tact="forward">Forward to ' + esc(name(c.to_company)) + '</button><button class="btn" data-tact="return">Return to ' + esc(name(c.from_company)) + '</button></div>' + reasonSel + note + '</div>';
    if (c.holder === v && c.status === 'with_owner' && r === 'owner')
      return '<div class="card sec"><div class="sec-h"><h3>Your step: decide</h3></div><div class="acts"><button class="btn primary" data-tact="approve">Approve</button><button class="btn" data-tact="reject">Reject</button><button class="btn" data-tact="return">Return to the architect</button></div>' + reasonSel + note + '</div>';
    return '<div class="card sec"><p style="margin:0;color:var(--muted)">With ' + esc(name(c.holder)) + '. You can comment.</p>' + note + comment + '</div>';
  }
  function amountEdit() { return '<div class="grid" style="grid-template-columns:repeat(2,minmax(0,1fr))"><div class="fd"><label><span>Amount ($)</span></label><div class="inp"><input id="tamount" inputmode="decimal" value="' + (T.c.amount == null ? '' : T.c.amount) + '"></div></div><div class="fd"><label><span>Days</span></label><div class="inp"><input id="tdays" inputmode="numeric" value="' + (T.c.days || 0) + '"></div></div></div>'; }
  function timePanel() {
    var c = T.c; if (c.tier !== 'proposal' || !c.days) return '';
    var last = T.evs.filter(function (e) { return e.kind === 'schedule'; }).slice(-1)[0], p = last && last.payload || {};
    var can = c.from_company === me() && OPEN[c.status];
    return '<div class="card sec" style="margin-top:16px"><div class="sec-h"><h3>Time</h3><span class="fine">' + c.days + ' days claimed</span></div>' +
      (last ? '<div class="tblock"><div><span>On the critical path</span><b>' + (p.critical ? 'Yes' : 'No') + '</b></div><div><span>Days it adds</span><b>' + (p.days == null ? '—' : p.days) + '</b></div><div><span>Extension</span><b>' + (p.extension == null ? '—' : p.extension + ' days') + '</b></div><div><span>Delay cost</span><b>' + money(p.cost) + '</b></div></div><p class="fine" style="margin:8px 0 0">Analyzed ' + when(last.created_at) + ' against ' + esc(p.schedule || 'the schedule') + '.</p>'
        : '<p class="fine" style="margin:0">Not analyzed yet. A delay counts only if the work is on the critical path; the analysis inserts the change’s activities into the current schedule and compares finish dates.</p>') +
      (can ? '<div class="acts" style="margin-top:10px"><button class="btn sm" data-tdelay="1">' + (last ? 'Analyze again' : 'Analyze the delay') + '</button></div>' : '') + '</div>';
  }
  function eventsHtml(evs) {
    if (!evs.length) return '<p class="fine" style="margin:0">Nothing yet.</p>';
    return '<ol class="timeline">' + evs.map(function (e) {
      var who = e.actor && people[e.actor] ? people[e.actor].email : e.actor ? '' : 'field link';
      return '<li class="ev ' + e.kind + '"><div class="ev-h"><span class="who ' + (e.ai ? 'ai' : /check|confirm/.test(e.kind) || (e.payload || {}).built_by === 'code' ? 'computed' : 'person') + '">' + esc(name(e.company_id)) + '</span><b>' + esc(KIND[e.kind] || e.kind) + '</b>' +
        (e.reason ? '<span class="tagr chk">' + esc(REASON[e.reason] || e.reason) + '</span>' : '') + (e.ai ? '<button class="tagr ai" data-receipt="' + e.id + '">AI · receipt</button>' : '') + '<span class="fine">' + when(e.created_at) + (who ? ' · ' + esc(who) : '') + '</span></div>' +
        (e.body ? '<p class="evb">' + esc(e.body.length > 900 ? e.body.slice(0, 897) + '…' : e.body) + '</p>' : '') + '</li>';
    }).join('') + '</ol>';
  }
  function post(kind, extra) {
    var c = T.c, row = Object.assign({ project_id: c.project_id, change_id: c.id, company_id: me(), kind: kind }, extra || {});
    var b = document.getElementById('tbody'); if (b && b.value.trim() && row.body == null) row.body = b.value.trim();
    return q(P.sb().from('events').insert(row));
  }

  /* ---------- the evidence trail: what led to this change, built by code from the record's links ---------- */
  var REL = { caused_by: 'Caused by', answered_by: 'Answered by', evidence_for: 'Site record', discussed: 'Discussed at', cites: 'Governed by', affects: 'Schedule work', supersedes: 'Changes' };
  function trail(c) {
    if (!c.document_id) return Promise.resolve(null);
    var sb = P.sb(), pid = c.project_id, co = c.document_id;
    return q(sb.from('links').select('*').eq('project_id', pid).or('from_doc.eq.' + co + ',to_doc.eq.' + co)).then(function (l1) {
      var causes = l1.filter(function (l) { return l.from_doc === co && l.relation === 'caused_by'; }).map(function (l) { return l.to_doc; });
      var hop = causes.length ? q(sb.from('links').select('*').eq('project_id', pid).in('from_doc', causes)) : Promise.resolve([]);
      var hop2 = causes.length ? q(sb.from('links').select('*').eq('project_id', pid).in('to_doc', causes)) : Promise.resolve([]);
      return Promise.all([hop, hop2]).then(function (r) {
        var all = l1.concat(r[0].filter(function (l) { return /answered_by|cites/.test(l.relation); }), r[1].filter(function (l) { return l.relation === 'discussed'; }));
        var docIds = {}, pieceIds = {};
        all.forEach(function (l) { [l.from_doc, l.to_doc].forEach(function (d) { if (d) docIds[d] = 1; }); [l.from_piece, l.to_piece].forEach(function (p) { if (p) pieceIds[p] = 1; }); });
        return Promise.all([q(sb.from('documents').select('*').in('id', Object.keys(docIds))), Object.keys(pieceIds).length ? q(sb.from('pieces').select('id,section,body,piece_date,document_id').in('id', Object.keys(pieceIds))) : Promise.resolve([])])
          .then(function (d) { var D = {}, Pc = {}; d[0].filter(P.sees.doc).forEach(function (x) { D[x.id] = x; }); d[1].forEach(function (x) { if (D[x.document_id]) Pc[x.id] = x; }); return { links: all, D: D, P: Pc, co: co }; });
      });
    });
  }
  function trailItems(tr) {
    var events = [], governs = [], work = [], seen = {};
    if (!tr) return { events: events, governs: governs, work: work };
    tr.links.forEach(function (l) {
      var other = l.from_doc === tr.co ? l.to_doc : l.to_doc === tr.co ? l.from_doc : (l.relation === 'answered_by' ? l.to_doc : l.from_doc);
      var piece = tr.P[l.from_doc === other ? l.from_piece : l.to_piece] || null, d = tr.D[other]; if (!d) return;
      var k = other + '|' + (piece ? piece.id : '') + '|' + l.relation; if (seen[k]) return; seen[k] = 1;
      var item = { d: d, piece: piece, rel: l.relation, date: (piece && piece.piece_date) || d.issued_on || '' };
      if (l.relation === 'cites') governs.push(item); else if (l.relation === 'affects') work.push(item); else events.push(item);
    });
    events.sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
    return { events: events, governs: governs, work: work };
  }
  function cite(x) { return (x.d.number || x.d.title) + (x.piece && x.piece.section ? ' ' + x.piece.section : ''); }
  function trailHtml(tr) {
    if (!tr) return '<p class="fine" style="margin:0">Not tied to a change order document in the record yet.</p>';
    var t = trailItems(tr);
    function li(x) {
      return '<li class="ev"><div class="ev-h"><span class="who computed">' + esc(REL[x.rel] || x.rel) + '</span><b><button class="link" data-dopen="' + x.d.id + '">' + esc(x.d.number || x.d.title) + '</button></b>' + (x.piece && x.piece.section ? '<span class="fine">' + esc(x.piece.section) + '</span>' : '') + '<span class="fine">' + esc(x.date) + '</span></div>' +
        (x.piece ? '<p class="quote-line">“' + esc(x.piece.body.length > 240 ? x.piece.body.slice(0, 237) + '…' : x.piece.body) + '”</p>' : '<p>' + esc(x.d.title) + '</p>') + '</li>';
    }
    return (t.events.length ? '<ol class="timeline">' + t.events.map(li).join('') + '</ol>' : '<p class="fine">No events linked yet.</p>') +
      (t.governs.length ? '<div class="sec-h" style="margin-top:16px"><h3>Terms that govern it</h3></div><ul class="govern">' + t.governs.map(function (x) { return '<li><button class="link" data-dopen="' + x.d.id + '">' + esc(cite(x)) + '</button>' + (x.piece ? '<span>' + esc(x.piece.body.length > 130 ? x.piece.body.slice(0, 127) + '…' : x.piece.body) + '</span>' : '') + '</li>'; }).join('') + '</ul>' : '') +
      '<p class="fine" style="margin-top:12px">Built by code from the record’s links. Only documents ' + esc(name(me())) + ' may see are shown. Who is responsible is for the parties to decide.</p>';
  }

  /* ---------- the steps' actions ---------- */
  function noticeText(c) {
    var nd = noticeDays(c), cause = c.cause || {};
    return 'Notice of Potential Change, ' + c.number + ': ' + c.title + '\nTo: ' + name(c.to_company) + (P.byRole('architect')[0] ? ' and ' + name(P.byRole('architect')[0]) : '') + '\nFrom: ' + name(c.from_company) +
      '\n\nUnder ' + (nd ? nd.clause : 'the contract') + ', we give notice that ' + (cause.type ? 'a ' + cause.type.toLowerCase() : 'an event') + (cause.reference ? ' (' + cause.reference + ')' : '') + (cause.event_date ? ' on ' + day(cause.event_date) : '') + ' may change the cost' + (c.days ? ' and time' : '') + ' of the work. A change proposal will follow.';
  }
  function bundle(subs, prop) {
    var sb = P.sb(), v = me();
    return P.q(sb.from('changes').select('*').eq('id', prop.id).single()).then(function (fresh) {
      var reqs = ((fresh.meta || {}).requests || []).concat(subs.map(function (s) { return { number: s.number, company: name(s.from_company), amount: +s.amount || 0 }; }));
      return P.q(sb.from('changes').update({ meta: Object.assign({}, fresh.meta || {}, { requests: reqs }) }).eq('id', prop.id));
    }).then(function () {
      return subs.reduce(function (p, s) {
        return p.then(function () { return P.q(sb.from('changes').update({ parent_id: prop.id }).eq('id', s.id)); })
          .then(function () { return P.q(sb.from('events').insert({ project_id: s.project_id, change_id: s.id, company_id: v, kind: 'bundle', body: 'Put in ' + prop.number + '.' })); })
          .then(function () { return P.q(sb.from('events').insert({ project_id: s.project_id, change_id: prop.id, company_id: v, kind: 'bundle', body: s.number + ' from ' + name(s.from_company) + ', ' + money(s.amount) + '.' })); });
      }, Promise.resolve());
    });
  }
  function runChecks() {
    var c = T.c;
    if (!T.cs) return Promise.reject(new Error('No priced cover sheet for ' + c.number + ' yet. Price it with the quick check first.'));
    var K = window.ClauseChecks, cs = K.checksheet(T.cs, A.C()), n = cs.counts;
    var fails = cs.rows.filter(function (r) { return r.status === 'fail'; }).map(function (r) { return '§ ' + r.section + ': ' + K.plain(r, 'gc', A.C()).title; });
    var body = n.pass + ' checks passed, ' + n.fail + ' to fix, ' + n.person + ' for a person.' + (cs.dollars_at_issue > 0 ? ' ' + K.money(cs.dollars_at_issue) + ' at issue.' : '') + (fails.length ? '\n' + fails.join('\n') : '') + '\nChecked by code against ' + A.C().name + '.';
    return post('check', { body: body, payload: { findings: n.fail, counts: n, dollars_at_issue: cs.dollars_at_issue, contract: A.C().name, failed: fails } });
  }
  function confirmModal() {
    var c = T.c, cs = T.cs && T.cs.cover_sheet;
    var rows = cs ? [['CM direct costs', cs.cm_direct_costs], ['Subcontractor quotes', cs.subcontractor_quotes], ['Fee (' + Math.round((cs.fee_rate || 0) * 1000) / 10 + '%)', cs.fee], ['Bond and insurance', cs.bond_and_insurance], ['B&O tax', cs.bo_tax], ['Permit fees', cs.permit_fees], ['Site services at cost (NSS)', cs.nss_items], ['General conditions items (SGC)', cs.sgc_items], ['Extended general conditions (time)', cs.extended_sgc_time]].filter(function (x) { return +x[1]; }) : [];
    modal('Confirm the numbers', 'Step 4 · ' + c.number, (cs ? '<table class="tbl"><tbody>' + rows.map(function (x) { return '<tr><td>' + esc(x[0]) + '</td><td class="r">' + money(x[1]) + '</td></tr>'; }).join('') + '<tr class="tot"><td><b>Total requested</b></td><td class="r"><b>' + money(cs.total_requested) + '</b></td></tr></tbody></table>' + (T.kids.length ? '<p class="fine">Sub requests in it: ' + T.kids.map(function (k) { return esc(k.number) + ' ' + money(k.amount); }).join(', ') + '.</p>' : '')
      : amountEdit()) + '<p class="fine">Read from the priced cover sheet. If a number is wrong, fix it in the quick check before confirming.</p>',
      [['Confirm these numbers', 'primary', function () { var amt = cs ? cs.total_requested : A.num((document.getElementById('tamount') || {}).value); return P.q(P.sb().from('changes').update({ amount: amt }).eq('id', c.id)).then(function () { return post('confirm', { body: 'Total ' + money(amt) + ' confirmed.', payload: { total: amt } }); }); }]]);
  }

  /* ---------- W7 the AI step: draft, citations, receipt ---------- */
  var savedRuns = null;
  function loadSavedRuns() { if (savedRuns) return Promise.resolve(savedRuns); return fetch('/record/results/draft_llama3.1_8b.json').then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }).then(function (j) { savedRuns = j || { rows: [] }; return savedRuns; }); }
  function draftFromRecord() {
    var c = T.c, t = trailItems(T.trail), note = (T.evs.filter(function (x) { return x.kind === 'note'; })[0] || {}).body || '';
    var cites = [], lines = ['Change proposal ' + c.number + ': ' + c.title, ''];
    if (note) lines.push(note, '');
    t.events.filter(function (x) { return x.rel === 'caused_by'; }).forEach(function (x) { cites.push(cite(x)); lines.push('Cause: ' + cite(x) + (x.piece ? ': “' + x.piece.body.slice(0, 200) + (x.piece.body.length > 200 ? '…' : '') + '”' : '') + ' [' + cites.length + ']'); });
    t.events.filter(function (x) { return x.rel === 'evidence_for' || x.rel === 'discussed'; }).slice(0, 3).forEach(function (x) { cites.push(cite(x)); lines.push('Record: ' + cite(x) + ' [' + cites.length + ']'); });
    var gov = t.governs.map(cite).filter(function (x, i, a) { return a.indexOf(x) === i; });
    if (gov.length) { gov.forEach(function (g) { cites.push(g); }); lines.push('', 'Priced and noticed under: ' + gov.map(function (g, i) { return g + ' [' + (cites.length - gov.length + i + 1) + ']'; }).join('; ') + '.'); }
    if (T.kids.length) lines.push('', 'Includes: ' + T.kids.map(function (k) { return k.number + ' (' + name(k.from_company) + ', ' + money(k.amount) + ')'; }).join('; ') + '.');
    return { text: lines.join('\n'), cites: cites };
  }
  function aiDraft() {
    var c = T.c, note = (T.evs.filter(function (x) { return x.kind === 'note'; })[0] || {}).body || c.title;
    if (A.reader()) return fetch('/api/draft', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ note: note, exclude: [c.number] }) }).then(function (r) { return r.json(); }).then(function (res) {
      if (res.error) throw new Error(res.error);
      return { model: res.model, where: 'on this computer', live: true, scope: res.draft.scope || '', cites: [res.cause && (res.cause.number || res.cause.doc)].concat((res.governing || []).map(function (g) { return g.id.replace('|', ' § '); })).filter(Boolean), notes: res.notes || [], inputs: res.candidates || null };
    });
    return loadSavedRuns().then(function (j) {
      var row = (j.rows || []).filter(function (x) { return x.id === c.number && x.variant === 'plain'; })[0];
      if (!row) return null;
      return { model: j.meta.model, where: 'saved run from ' + j.meta.date + ' (online, the model can’t run here)', live: false, scope: row.scope || '', cites: [row.cause].concat(row.governing || []).filter(Boolean).map(function (g) { return String(g).replace('|', ' § '); }), notes: row.notes || [], inputs: row.candidates || null };
    });
  }
  // Code checks each citation against the record the viewer can see: the document, and the section if one is named.
  function verifyCites(cites) {
    return q(P.sb().from('documents').select('*').eq('project_id', ctx().project.id)).then(function (docs) {
      var vis = docs.filter(function (d) { return d.number && P.sees.doc(d); }).sort(function (a, b) { return b.number.length - a.number.length; });
      var out = cites.map(function (x) {
        var s = String(x), d = vis.filter(function (v) { return s === v.number || s.indexOf(v.number + ' ') === 0; })[0];
        return { cite: x, doc: d || null, section: d ? s.slice(d.number.length).replace(/^\s*§?\s*/, '').trim() : '' };
      });
      var ids = out.filter(function (x) { return x.doc && x.section; }).map(function (x) { return x.doc.id; });
      if (!ids.length) return out;
      return q(P.sb().from('pieces').select('document_id,section').in('document_id', ids)).then(function (ps) {
        out.forEach(function (x) {
          if (!x.doc || !x.section) return;
          var hit = ps.some(function (p) { return p.document_id === x.doc.id && String(p.section || '').trim() === x.section; });
          if (!hit) { x.missing = 'section ' + x.section + ' is not in ' + x.doc.number; x.doc = null; }
        });
        return out;
      });
    });
  }
  // Code: do the sub requests add up, against their own lines and against the cover sheet?
  function rollup() {
    var out = [], kids = T.kids, sum = kids.reduce(function (s, k) { return s + (+k.amount || 0); }, 0);
    kids.forEach(function (k) { var ls = (k.meta || {}).lines || []; if (ls.length) { var t = ls.reduce(function (s, l) { return s + (+l.amount || 0); }, 0); if (Math.abs(t - (+k.amount || 0)) > 0.5) out.push(k.number + ': its lines add to ' + money(t) + ' but the total reads ' + money(k.amount) + '.'); } });
    var cq = T.cs && T.cs.cover_sheet ? +T.cs.cover_sheet.subcontractor_quotes : null;
    if (kids.length && cq != null && Math.abs(sum - cq) > 0.5) out.push('Sub requests total ' + money(sum) + '; the cover sheet carries ' + money(cq) + ' for subcontractor quotes (' + money(Math.abs(sum - cq)) + ' apart).');
    return out;
  }
  function draftStep() {
    var code = draftFromRecord();
    A.toast('Drafting…');
    aiDraft().catch(function () { return null; }).then(function (ai) {
      if (!ai) return { ai: null, text: code.text, cites: code.cites };
      var text = (ai.scope ? 'Scope: ' + ai.scope + '\n\n' : '') + code.text + (ai.notes.length ? '\n\nCode flagged in the AI draft: ' + ai.notes.join(' ') : '');
      return { ai: ai, text: text, cites: ai.cites.concat(code.cites.filter(function (x) { return ai.cites.indexOf(x) < 0; })) };
    }).then(function (d) {
      return verifyCites(d.cites).then(function (vc) { d.verified = vc; return d; });
    }).then(function (d) { aiModal(d); }).catch(fail);
  }
  function receiptHtml(d) {
    var ok = d.verified.filter(function (x) { return x.doc; }).length;
    return '<div class="receipt"><div class="sec-h"><h3>Receipt</h3></div><dl>' +
      '<dt>Drafted by</dt><dd>' + (d.ai ? esc(d.ai.model) + ', ' + esc(d.ai.where) : 'Code, from the record’s links (no AI step)') + '</dd>' +
      '<dt>Where it ran</dt><dd>' + (d.ai ? (d.ai.live ? 'This computer. The contract text didn’t leave it.' : 'Our own test run of a free open model; nothing was sent to outside AI services.') : 'In this browser.') + '</dd>' +
      '<dt>Citations</dt><dd>' + ok + ' of ' + d.verified.length + ' found in the record' + (ok < d.verified.length ? ' <span class="badge fail">' + (d.verified.length - ok) + ' not found</span>' : '') + '</dd>' +
      (d.ai && d.ai.inputs ? '<dt>Inputs</dt><dd>' + esc(String(d.ai.inputs)) + ' record entries offered</dd>' : '') + '</dl></div>';
  }
  function aiModal(d, readOnly) {
    var cites = '<ol class="cites">' + d.verified.map(function (x, i) { return '<li class="' + (x.doc ? 'ok' : 'miss') + '">' + (x.doc ? '<button class="link" data-dopen="' + x.doc.id + '">' + esc(x.cite) + '</button>' : '<span style="color:var(--red)">' + esc(x.cite) + ' (' + esc(x.missing || 'not in the record') + ')</span>') + '</li>'; }).join('') + '</ol>';
    var body = '<div class="cols" style="--cols:minmax(0,1.6fr) minmax(0,1fr)"><div>' + (readOnly ? '<pre class="draft' + (d.ai ? ' ai' : '') + '">' + esc(d.text) + '</pre>' : '<div class="inp' + (d.ai ? ' ai' : '') + '" style="height:auto"><textarea id="aidraft" rows="14">' + esc(d.text) + '</textarea></div>') +
      '<div class="sec-h" style="margin-top:12px"><h3>Citations</h3></div>' + cites + '</div><div>' + receiptHtml(d) + '</div></div>';
    if (readOnly) return modal('AI step detail', 'Receipt', body, []);
    modal(d.ai ? 'AI draft' : 'Draft from the record', 'Step 3 · ' + T.c.number, body, [
      ['Accept', 'primary', function () {
        var text = document.getElementById('aidraft').value, edited = text !== d.text;
        return post('draft', { body: text, ai: d.ai ? { model: d.ai.model, where: d.ai.where, live: d.ai.live, citations: d.verified.map(function (x) { return x.cite; }), found: d.verified.filter(function (x) { return x.doc; }).length, inputs: d.ai.inputs, output: d.text, edited: edited } : null,
          payload: { built_by: d.ai ? 'ai' : 'code', citations: d.verified.map(function (x) { return x.cite; }), edited: edited } });
      }],
      ['Reject', 'ghost', function () { return post('note', { body: 'Rejected the ' + (d.ai ? 'AI' : 'code') + ' draft.', ai: d.ai ? { model: d.ai.model, where: d.ai.where, live: d.ai.live, citations: d.verified.map(function (x) { return x.cite; }), output: d.text, rejected: true } : null }); }]
    ]);
  }
  function showReceipt(id) {
    var e = T && T.evs.filter(function (x) { return String(x.id) === String(id); })[0]; if (!e || !e.ai) return;
    verifyCites(e.ai.citations || []).then(function (vc) {
      aiModal({ ai: { model: e.ai.model, where: e.ai.where, live: e.ai.live, inputs: e.ai.inputs }, text: (e.ai.output || e.body || '') + (e.ai.edited ? '\n\n— Edited by a person before acceptance. Accepted text:\n' + e.body : '') + (e.ai.rejected ? '\n\n— Rejected by ' + name(e.company_id) + '.' : ''), verified: vc }, true);
    }).catch(fail);
  }
  function modal(title, eyebrow, body, buttons) {
    var m = document.createElement('div'); m.className = 'modal';
    m.innerHTML = '<div class="modal-card" style="width:min(980px,100%)"><div class="modal-h"><div><span class="eyebrow">' + esc(eyebrow) + '</span><h2>' + esc(title) + '</h2></div><button class="btn ghost sm" data-mclose="1">Close</button></div>' + body +
      '<div class="acts" style="margin-top:16px">' + buttons.map(function (b, i) { return '<button class="btn ' + b[1] + '" data-mb="' + i + '">' + esc(b[0]) + '</button>'; }).join('') + '</div></div>';
    document.body.appendChild(m);
    m.addEventListener('click', function (e) {
      var b = e.target.closest('[data-mb]'), d = e.target.closest('[data-dopen]');
      if (d) { m.remove(); store('cs_doc', d.dataset.dopen); return A.go('doc'); }
      if (b) { var fn = buttons[+b.dataset.mb][2]; b.disabled = true; Promise.resolve(fn()).then(function () { m.remove(); A.toast('Saved to the activity log.'); V.change(); }).catch(function (er) { b.disabled = false; fail(er); }); return; }
      if (e.target === m || e.target.closest('[data-mclose]')) m.remove();
    });
  }

  /* ---------- delay analysis, handed to the delay tool and back ---------- */
  function startDelay() {
    var c = T.c;
    q(P.sb().from('schedule_versions').select('*').eq('project_id', c.project_id).order('created_at')).then(function (vs) {
      if (!vs.length) throw new Error('Add the project schedule in 04 Schedule first.');
      // The latest version that doesn't already include this change: a time impact analysis inserts the change into the schedule as it stood before it.
      var before = vs.filter(function (x) { return (x.caused_by || []).indexOf(c.number) < 0; }), v = before[before.length - 1] || vs[vs.length - 1], model = window.ClauseSchedule.fromJSON ? window.ClauseSchedule.fromJSON(v.data) : v.data;
      var rec = { id: 'proj-' + v.id, name: v.label + ' (' + ctx().project.name + ')', label: v.is_baseline ? 'Baseline' : 'Update', file: 'project', saved: Date.now(), model: normSched(v.data, v.label) };
      var L = (store('cs_schedules') || []).filter(function (x) { return x.id !== rec.id; }); L.unshift(rec); store('cs_schedules', L.slice(0, 8)); store('cs_sched_active', rec.id);
      store('cs_delay_prefill', { id: c.number, title: c.title, claimed_days: c.days, narrative: (T.evs.filter(function (x) { return x.kind === 'note'; })[0] || {}).body || '', caseId: (c.meta || {}).case_id || c.number, fromCase: true });
      store('cs_delay_return', { change: c.id, number: c.number, version: v.id, label: v.label });
      A.go('delay');
    }).catch(fail);
  }
  function normSched(d, label) {
    var m = JSON.parse(JSON.stringify(d)); m.source = m.source && typeof m.source === 'object' ? m.source : { format: 'manual', has_logic: true };
    if (m.source.has_logic == null) m.source.has_logic = (m.relationships || []).length > 0; if (!m.source.format) m.source.format = 'manual';
    m.name = m.name || label; return m;
  }
  // Called by views-time.js when a delay result is confirmed.
  V.delayDone = function (DX, d, cost) {
    var back = store('cs_delay_return'); if (!back) return Promise.resolve(false);
    store('cs_delay_return', null);
    var r = DX.result || {};
    var row = { project_id: ctx().project.id, change_id: back.change, company_id: me(), kind: 'schedule',
      body: 'Delay analyzed against ' + back.label + ': ' + (r.delay_calendar_days || 0) + ' calendar days, ' + (r.fragnet_critical ? 'on' : 'not on') + ' the critical path; ' + d.extensionDays + ' days extension; ' + M(cost || 0) + '.',
      payload: { days: r.delay_calendar_days || 0, work_days: r.delay_workdays || 0, critical: !!r.fragnet_critical, extension: d.extensionDays, cost: cost || 0, schedule: back.label, log: DX.log.concat(d.steps) },
      ai: DX.fragSrc === 'ai' ? { model: DX.fragModel, where: 'saved run (fragnet draft)', live: false, citations: [], output: (DX.frag.activities || []).map(function (a) { return a.id + ' ' + a.name + ' (' + a.duration + 'd)'; }).join('; '), edited: !!DX.fragEdited } : null };
    return q(P.sb().from('events').insert(row)).then(function () { store('cs_change', back.change); A.toast('Saved to ' + back.number + '.'); A.go('change'); return true; });
  };
  V.delayUpdate = function (DX, model, name2) {
    var back = store('cs_delay_return') || {}; if (!ctx()) return Promise.resolve(false);
    return q(P.sb().from('schedule_versions').insert({ project_id: ctx().project.id, label: name2, data_date: model.data_date || null, data: model, caused_by: [DX.claim.id].filter(Boolean) })).then(function () { return true; });
  };

  /* ---------- 02 Record (W5) ---------- */
  function splitPieces(kind, text, date) {
    var out = [];
    if (kind === 'contract' || kind === 'spec') {
      var CT = window.ClauseContract, by = {}, order = [];
      CT.sentences(text).forEach(function (x) { var k = x.section || '—'; if (!by[k]) { by[k] = []; order.push(k); } by[k].push(x.text); });
      order.forEach(function (k, i) { out.push({ ordinal: i + 1, section: k === '—' ? null : k, body: by[k].join(' '), piece_date: date || null }); });
      return out;
    }
    var sec = null, buf = [];
    function flush() { var b = buf.join(' ').replace(/\s+/g, ' ').trim(); if (b) out.push({ ordinal: out.length + 1, section: sec, body: b, piece_date: date || null }); buf = []; }
    String(text).split(/\r?\n/).forEach(function (line) {
      var m = line.match(/^\s*(?:#+\s*)?(question|answer|response|suggested solution|description|action|reviewer comments?|weather|crew counts?|work performed|issues?(?:\/delays)?|item\s+[\d.]+)\s*[:.-]\s*(.*)$/i);
      if (m) { flush(); sec = m[1].replace(/^\w/, function (c) { return c.toUpperCase(); }); if (m[2]) buf.push(m[2]); return; }
      if (!line.trim()) { flush(); return; }
      buf.push(line.trim());
    });
    flush();
    return out;
  }
  P.splitPieces = splitPieces;
  V.record = function () {
    gate(function (C) {
      q(P.sb().from('documents').select('id,kind,visibility,contract_id,author_company').eq('project_id', C.project.id)).then(function (all) {
        var docs = all.filter(P.sees.doc), counts = {}; docs.forEach(function (d) { counts[d.kind] = (counts[d.kind] || 0) + 1; });
        var qv = store('cs_rq') || '', mineK = Object.keys(C.contracts).map(function (k) { return C.contracts[k]; }).filter(function (k) { return R.partyTo(k, me()); });
        app.innerHTML = sheet('02 Record', 'Project record', '<p style="margin:-6px 0 16px;color:var(--muted)">' + docs.length + ' documents ' + esc(name(me())) + ' can see' + (docs.length ? ': ' + Object.keys(counts).map(function (k) { return counts[k] + ' × ' + (DOCKIND[k] || k); }).join(', ') : '') + '. Answers below are quoted from the record, never written by AI.</p>' +
          '<form id="rsearch" class="grid" style="grid-template-columns:minmax(0,1fr) auto;gap:10px;max-width:760px"><div class="inp"><input id="rq" value="' + esc(qv) + '" placeholder="Ask or search, e.g. when was notice given about the mastic"></div><button class="btn primary" type="submit">Search the record</button></form>' +
          '<div class="cols" style="--cols:minmax(0,1.6fr) minmax(0,1fr);margin-top:18px"><div id="rres"><div class="card sec"><p style="margin:0;color:var(--muted)">Search finds the exact sentences in the RFIs, ASIs, submittals, daily reports, approved minutes, contracts and specs ' + esc(name(me())) + ' may see.</p></div></div>' +
          '<div><div class="card sec"><div class="sec-h"><h3>Add a document</h3></div><form id="rup" class="grid"><div class="fd"><label><span>Kind</span></label><div class="inp sel"><select id="ukind">' +
          ['rfi', 'asi', 'submittal', 'daily_report', 'minutes', 'contract', 'spec', 'change_order', 'other'].map(function (k) { return '<option value="' + k + '">' + DOCKIND[k] + '</option>'; }).join('') + '</select></div></div>' +
          '<div class="fd"><label><span>Number</span></label><div class="inp"><input id="unum" placeholder="e.g. RFI-241"></div></div>' +
          '<div class="fd full"><label><span>Title</span></label><div class="inp"><input id="utitle" required></div></div>' +
          '<div class="fd"><label><span>Dated</span></label><div class="inp"><input id="udate" type="date"></div></div>' +
          '<div class="fd"><label><span>Who sees it</span></label><div class="inp sel"><select id="uvis"><option value="project">Everyone on the project</option>' + mineK.map(function (k) { return '<option value="k:' + k.id + '">Parties to ' + esc(k.title) + '</option>'; }).join('') + '<option value="company">Only ' + esc(name(me())) + '</option></select></div></div>' +
          '<div class="fd full"><label><span>File (PDF with text, .txt or .md)</span></label><input id="ufile" type="file" accept=".pdf,.txt,.md" required></div>' +
          '<div class="fd full"><label class="tog-row"><input type="checkbox" id="usub"> Approved meeting minutes only: these minutes were approved at a later meeting</label></div>' +
          '<div class="fd full"><button class="btn primary" type="submit">Add to the record</button></div></form></div>' +
          '<div class="card sec" style="margin-top:16px"><div class="sec-h"><h3>Procore</h3><span class="tagr none">not connected</span></div><p class="fine" style="margin:0">RFIs and change orders will come in from Procore through this same import once the developer account exists, read-only first. Each synced item keeps its Procore id, so a re-sync updates instead of duplicating.</p></div></div></div>');
        if (qv) search(qv);
      }).catch(fail);
    });
  };
  function search(text) {
    var C = ctx(), el = document.getElementById('rres'); if (!el) return;
    el.innerHTML = '<div class="card sec"><p class="fine" style="margin:0">Searching…</p></div>';
    q(P.sb().from('pieces').select('id,document_id,section,body,piece_date').eq('project_id', C.project.id).textSearch('search', text, { type: 'websearch' }).limit(60)).then(function (ps) {
      var ids = ps.map(function (p) { return p.document_id; }).filter(function (x, i, a) { return a.indexOf(x) === i; });
      return (ids.length ? q(P.sb().from('documents').select('*').in('id', ids)) : Promise.resolve([])).then(function (docs) {
        var D = {}; docs.filter(P.sees.doc).forEach(function (d) { D[d.id] = d; });
        var hits = ps.filter(function (p) { return D[p.document_id]; }).slice(0, 20);
        if (!hits.length) { el.innerHTML = '<div class="card sec"><p style="margin:0">Nothing in the record ' + esc(name(me())) + ' can see matches “' + esc(text) + '”. Try fewer or different words.</p></div>'; return; }
        var best = hits[0], bd = D[best.document_id];
        el.innerHTML = '<div class="card sec"><div class="sec-h"><h3>Answer, quoted</h3></div><p class="quote-line">“' + esc(best.body) + '”</p><p class="fine" style="margin:6px 0 0"><button class="link" data-dopen="' + bd.id + '">' + esc(bd.number || bd.title) + (best.section ? ' ' + esc(best.section) : '') + '</button> · ' + esc(DOCKIND[bd.kind] || bd.kind) + ' · ' + esc(best.piece_date || bd.issued_on || '') + '</p></div>' +
          '<div class="card sec" style="margin-top:12px"><div class="sec-h"><h3>' + hits.length + ' pieces found</h3></div><ol class="results">' + hits.map(function (p) { var d = D[p.document_id]; return '<li><div><button class="link" data-dopen="' + d.id + '">' + esc(d.number || d.title) + '</button>' + (p.section ? ' <span class="fine">' + esc(p.section) + '</span>' : '') + ' <span class="fine">' + esc(DOCKIND[d.kind] || d.kind) + '</span></div><p>' + esc(p.body.length > 300 ? p.body.slice(0, 297) + '…' : p.body) + '</p></li>'; }).join('') + '</ol></div>';
      });
    }).catch(fail);
  }
  function upload() {
    var C = ctx(), f = document.getElementById('ufile').files[0], kind = document.getElementById('ukind').value, vis = document.getElementById('uvis').value;
    if (kind === 'minutes' && !document.getElementById('usub').checked) return A.toast('Only approved minutes go in the record. Tick the box once they’re approved.');
    var date = document.getElementById('udate').value || null;
    var read = /\.pdf$/i.test(f.name) ? A.pdfText(f) : f.text();
    read.then(function (text) {
      if (text.replace(/\s/g, '').length < 40) throw new Error('No readable text in ' + f.name + '. A scanned PDF has no text layer.');
      var row = { project_id: C.project.id, kind: kind, number: document.getElementById('unum').value.trim() || null, title: document.getElementById('utitle').value.trim(), issued_on: date, author_company: me(),
        visibility: vis.indexOf('k:') === 0 ? 'contract' : vis, contract_id: vis.indexOf('k:') === 0 ? vis.slice(2) : null, source: 'upload', external_id: 'up:' + f.name + ':' + f.size + ':' + Date.now(), meta: { file_name: f.name } };
      var pieces = splitPieces(kind, text, date);
      var path = C.project.id + '/' + Date.now() + '-' + f.name.replace(/[^\w.-]+/g, '_'), sb = P.sb();
      var up = sb.storage ? sb.storage.from('documents').upload(path, f).then(function (r) { if (!r.error) row.file_path = path; }) : Promise.resolve();
      return up.then(function () { return q(sb.from('documents').insert(row).select().single()); }).then(function (d) {
        return q(sb.from('pieces').insert(pieces.map(function (p) { return Object.assign({ project_id: C.project.id, document_id: d.id, company_id: me() }, p); }))).then(function () {
          return q(sb.from('events').insert({ project_id: C.project.id, company_id: me(), kind: 'link', body: 'Added ' + (d.number || d.title) + ' to the record (' + pieces.length + ' pieces).', payload: { document_id: d.id } }));
        }).then(function () { A.toast('Added ' + (d.number || d.title) + ': ' + pieces.length + ' pieces.'); V.record(); });
      });
    }).catch(fail);
  }
  V.doc = function () {
    gate(function (C) {
      var id = store('cs_doc'); if (!id) return A.go('record');
      var sb = P.sb();
      q(sb.from('documents').select('*').eq('id', id).maybeSingle()).then(function (d) {
        if (!d || !P.sees.doc(d)) { app.innerHTML = sheet('02 Record', 'Not visible', '<div class="banner warn"><span>' + esc(name(me())) + ' can’t see this document under its contracts. <a class="link" href="#record">Back to the record</a></span></div>'); return; }
        return Promise.all([q(sb.from('pieces').select('*').eq('document_id', id).order('ordinal')), q(sb.from('links').select('*').eq('project_id', C.project.id).or('from_doc.eq.' + id + ',to_doc.eq.' + id))]).then(function (r) {
          var ps = r[0], ls = r[1], other = ls.map(function (l) { return l.from_doc === id ? l.to_doc : l.from_doc; });
          return (other.length ? q(sb.from('documents').select('*').in('id', other)) : Promise.resolve([])).then(function (od) {
            var O = {}; od.filter(P.sees.doc).forEach(function (x) { O[x.id] = x; });
            var rel = ls.map(function (l) { var o = O[l.from_doc === id ? l.to_doc : l.from_doc]; return o ? '<li><span class="fine">' + esc(REL[l.relation] || l.relation) + '</span> <button class="link" data-dopen="' + o.id + '">' + esc(o.number || o.title) + '</button></li>' : ''; }).filter(Boolean).filter(function (x, i, a) { return a.indexOf(x) === i; }).join('');
            var vis = d.visibility === 'project' ? 'Everyone on the project' : d.visibility === 'company' ? 'Only ' + name(d.author_company) : 'Parties to ' + ((C.contracts[d.contract_id] || {}).title || 'a contract');
            app.innerHTML = sheet('02 Record', (d.number ? d.number + ' · ' : '') + d.title, '<p style="margin:-6px 0 16px;color:var(--muted)">' + esc(DOCKIND[d.kind] || d.kind) + (d.issued_on ? ' · ' + esc(d.issued_on) : '') + (d.author_company ? ' · from ' + esc(name(d.author_company)) : '') + ' · ' + (d.source === 'synthetic' ? 'synthetic' : esc(d.source)) + ' · seen by: ' + esc(vis) + ' · <a class="link" href="#record">Back to search</a></p>' +
              '<div class="cols" style="--cols:minmax(0,1.6fr) minmax(0,1fr)"><div class="card sec"><ol class="pieces">' + ps.map(function (p) { return '<li><span class="fine">' + esc(p.section || p.ordinal) + '</span><p>' + esc(p.body) + '</p></li>'; }).join('') + '</ol></div>' +
              '<div class="card sec"><div class="sec-h"><h3>Linked</h3></div>' + (rel ? '<ul class="govern">' + rel + '</ul>' : '<p class="fine" style="margin:0">Nothing linked that you can see.</p>') + '</div></div>');
          });
        });
      }).catch(fail);
    });
  };

  /* ---------- 03 Contracts (W3) ---------- */
  function fmtVal(v) { if (v == null) return '—'; if (typeof v === 'boolean') return v ? 'Yes' : 'No'; if (Array.isArray(v)) return v.join(', '); if (typeof v === 'object') return Object.keys(v).map(function (k) { return k + ': ' + v[k]; }).join('; '); return String(v); }
  V.contracts = function () {
    gate(function (C) {
      var Ks = Object.keys(C.contracts).map(function (k) { return C.contracts[k]; }).filter(P.sees.contract);
      var sel = store('cs_contract_sel'), cur = Ks.filter(function (k) { return k.id === sel; })[0] || Ks.filter(function (k) { return R.partyTo(k, me()); })[0] || Ks[0];
      var prime = P.prime(), pn = prime ? P.term(prime, 'notice_days_by_cause') : null, primeDays = pn && typeof pn === 'object' ? Math.min.apply(null, Object.keys(pn).map(function (k) { return +pn[k]; })) : null;
      function node(k) { return '<li class="' + (cur && k.id === cur.id ? 'on' : '') + '"><button class="link" data-ksel="' + k.id + '">' + esc(k.title) + '</button><span class="fine">' + esc(name(k.up_company)) + ' ↔ ' + esc(name(k.down_company)) + '</span></li>'; }
      var subsK = Ks.filter(function (k) { return k.kind === 'sub'; }), design = Ks.filter(function (k) { return k.kind === 'design'; });
      var tree = '<ul class="ktree">' + Ks.filter(function (k) { return k.kind === 'prime'; }).map(function (k) { return node(k) + (subsK.length ? '<ul>' + subsK.map(node).join('') + '</ul>' : ''); }).join('') + design.map(node).join('') + '</ul>' +
        '<p class="fine" style="margin:12px 0 0">Contract type: <b>' + esc(P.TYPE[C.project.contract_type] || C.project.contract_type) + '</b>. You see the prime contract and the contracts ' + esc(name(me())) + ' is party to.</p>';
      var gaps = primeDays == null ? [] : subsK.map(function (k) { var sd = P.term(k, 'notice_days'); var g = R.flowdownGap(primeDays, sd == null ? null : +sd); return g ? { k: k, g: g, sd: sd } : null; }).filter(Boolean);
      var gapHtml = gaps.length ? '<div class="card sec" style="margin-top:16px"><div class="sec-h"><h3>Flow-down check</h3><span class="fine">code</span></div><ul class="qual">' + gaps.map(function (x) {
        return '<li class="' + (x.g.gap ? 'fail' : 'pass') + '"><span class="qd"></span><div><b>' + esc(name(x.k.down_company)) + '</b>: ' + x.sd + ' days to give notice, prime contract ' + primeDays + ' days (' + esc(primeClause('notice_days_by_cause')) + '). ' + (x.g.gap ? (x.g.margin < 0 ? 'The sub’s window is ' + (-x.g.margin) + ' day' + (x.g.margin === -1 ? '' : 's') + ' longer than the GC/CM’s own' : 'That leaves the GC/CM ' + x.g.margin + ' days to pass it up') + ': a flow-down gap. A late notice from this sub can arrive after the GC/CM’s deadline has passed.' : 'Leaves the GC/CM ' + x.g.margin + ' days to pass it up.') + '</div></li>';
      }).join('') + '</ul></div>' : '';
      var terms = cur ? Object.keys(cur.terms).map(function (key) { return cur.terms[key]; }) : [];
      var canConfirm = cur && R.partyTo(cur, me());
      var tt = terms.map(function (t) { return '<tr><td><b>' + esc(TERM[t.key] || t.key) + '</b></td><td>' + esc(fmtVal(t.value)) + '</td><td class="fine">' + esc(t.clause || '') + '</td><td class="fine">“' + esc(t.sentence || '') + '”</td><td>' + (t.confirmed_at ? '<span class="badge ok">confirmed</span>' : canConfirm ? '<button class="btn ghost sm" data-tconf="' + t.id + '">Confirm</button>' : '<span class="fine">—</span>') + '</td></tr>'; }).join('');
      app.innerHTML = sheet('03 Contracts', 'The contract chain', '<div class="cols" style="--cols:minmax(0,0.9fr) minmax(0,2fr)"><div><div class="card sec"><div class="sec-h"><h3>Contracts</h3></div>' + tree + '</div>' + gapHtml +
        (C.admin ? '<div class="card sec" id="addk" style="margin-top:16px"><div class="sec-h"><h3>Add a contract</h3></div>' + (Object.keys(C.companies).length < 2 ? '<p class="fine" style="margin:0">A contract is between two companies on the project. Invite the other company on 06 Project; once they sign in, add the contract here.</p>' :
          '<form id="newk" class="grid"><div class="fd full"><label><span>Title</span></label><div class="inp"><input id="ktitle" required placeholder="e.g. Subcontract: Plumbing"></div></div>' +
          '<div class="fd full"><label><span>Kind</span></label><div class="inp sel"><select id="kkind"><option value="prime">Prime: owner and GC/CM</option><option value="design">Design: owner and architect</option><option value="sub">Subcontract: GC/CM and a sub</option></select></div></div>' +
          '<div class="fd"><label><span>Upper party</span></label><div class="inp sel"><select id="kup">' + Object.keys(C.companies).map(function (id) { return '<option value="' + id + '">' + esc(C.companies[id].name) + ' (' + esc(P.ROLE[C.role[id]] || '') + ')</option>'; }).join('') + '</select></div></div><div class="fd"><label><span>Lower party</span></label><div class="inp sel"><select id="kdown">' + Object.keys(C.companies).map(function (id) { return '<option value="' + id + '">' + esc(C.companies[id].name) + ' (' + esc(P.ROLE[C.role[id]] || '') + ')</option>'; }).join('') + '</select></div></div>' +
          '<div class="fd full"><button class="btn sm" type="submit">Add the contract</button></div></form>') + '</div>' : '') +
        '<div class="card sec" style="margin-top:16px"><div class="sec-h"><h3>Read a contract’s terms</h3></div><p class="fine" style="margin:0 0 10px">Upload a contract and pick the sentence that states each term; we copy the number from it and you confirm it.</p>' + (canConfirm ? '<button class="btn sm" id="kread">Read the terms of ' + esc(cur.title) + '</button>' : '<a class="btn sm" href="#contract">Open the contract reader</a>') + '</div></div>' +
        '<div class="card sec"><div class="sec-h"><h3>' + esc(cur ? cur.title : 'No contract') + '</h3>' + (cur && cur.document_id ? '<button class="link" data-dopen="' + cur.document_id + '">Open the document</button>' : '') + '</div>' +
        (terms.length ? '<div class="tbl-wrap"><table class="tbl terms"><thead><tr><th>Term</th><th>Value</th><th>Clause</th><th>The sentence it came from</th><th></th></tr></thead><tbody>' + tt + '</tbody></table></div>' : '<p class="fine" style="margin:0">No terms read yet.</p>') +
        '<p class="fine" style="margin:12px 0 0">Every value is shown with the sentence it came from. A person confirms each before checks rely on it.</p></div></div>');
      var kr = document.getElementById('kread');
      if (kr) kr.onclick = function () { store('cs_reader_target', { contract: cur.id, project: C.project.id, title: cur.title }); A.go('contract'); };
      var nk = document.getElementById('newk');
      if (nk) nk.addEventListener('submit', function (e) {
        e.preventDefault();
        var kind = document.getElementById('kkind').value, up = document.getElementById('kup').value, down = document.getElementById('kdown').value;
        if (up === down) return A.toast('Pick two different companies.');
        var prime = P.prime();
        q(P.sb().from('contracts').insert({ project_id: C.project.id, kind: kind, up_company: up, down_company: down, parent_id: kind === 'sub' && prime ? prime.id : null, title: document.getElementById('ktitle').value.trim() }).select().single())
          .then(function (k) { store('cs_contract_sel', k.id); return P.loadCtx(C.project.id); }).then(function () { A.toast('Contract added. Now read its terms.'); V.contracts(); }).catch(fail);
      });
    });
  };

  /* ---------- 04 Schedule and delay (W4) ---------- */
  function loadSov() { return ctx() ? q(P.sb().from('sov_lines').select('*').eq('project_id', ctx().project.id)).then(function (ls) { return ls.filter(P.sees.sov); }).catch(function () { return []; }) : Promise.resolve([]); }
  // Cost per day of delay: the rate the prime contract states, and the time-based general conditions in the schedule of values
  // spread over the contract time, as a cross-check. The stated rate governs when there is one.
  function costPerDay(sov) {
    var r = R.costPerDay(sov, primeTerm('daily_delay_rate'), primeTerm('contract_days'));
    r.label = r.stated != null ? 'the contract’s daily rate (' + primeClause('daily_delay_rate') + ')' : r.spread ? 'general conditions ÷ contract days' : '';
    return r;
  }
  V.schedule = function () {
    gate(function (C) {
      Promise.all([q(P.sb().from('schedule_versions').select('*').eq('project_id', C.project.id).order('created_at')), loadSov(), loadChanges()]).then(function (r) {
        var vs = r[0], rate = costPerDay(r[1]), SE = window.ClauseSchedule;
        var vrows = vs.map(function (v) { var fin = '—'; try { fin = SE.cpm(normSched(v.data, v.label)).finish_date; } catch (e) {} return '<tr><td><b>' + esc(v.label) + '</b>' + (v.is_baseline ? ' <span class="badge ok">baseline</span>' : '') + '</td><td>' + day(v.data_date) + '</td><td>' + day(fin) + '</td><td>' + esc((v.caused_by || []).join(', ') || '—') + '</td><td>' + ((v.data.activities || []).length) + '</td></tr>'; }).join('');
        var timed = r[2].filter(function (c) { return c.tier === 'proposal' && c.days; });
        var money2 = rate.lines.length || rate.stated != null ? '<div class="card sec"><div class="sec-h"><h3>Cost per day of delay</h3><span class="fine">code</span></div><div class="tblock two">' +
          (rate.stated != null ? '<div><span>Stated in the contract</span><b>' + money(rate.stated) + '/day</b></div>' : '') + (rate.spread ? '<div><span>Schedule of values ÷ contract days</span><b>' + money(rate.spread) + '/day</b></div>' : '') + '</div>' +
          (rate.lines.length ? '<p class="fine" style="margin:10px 0 6px">Time-based general conditions (' + money(rate.total) + ') over ' + rate.days + ' contract days (' + esc(primeClause('contract_days')) + '):</p><table class="tbl"><tbody>' + rate.lines.map(function (l) { return '<tr><td class="code">' + esc(l.code || '') + '</td><td>' + esc(l.description) + '</td><td class="r">' + money(l.amount) + '</td></tr>'; }).join('') + '</tbody></table>' : '') +
          '<p class="fine" style="margin:8px 0 0">' + (rate.stated != null && rate.spread ? (Math.abs(rate.stated - rate.spread) < 1 ? 'They agree. ' : 'They differ by ' + money(Math.abs(rate.stated - rate.spread)) + ' a day. ') + 'The contract’s stated rate governs.' : rate.stated != null ? 'The contract’s stated rate governs.' : 'No rate stated in the contract, so the spread is used.') + '</p></div>'
          : '<div class="card sec"><p class="fine" style="margin:0">The schedule of values isn’t shared with ' + esc(name(me())) + '. Cost per day is between the owner and the GC/CM.</p></div>';
        app.innerHTML = sheet('04 Schedule', 'Schedule and delay', '<div class="cols" style="--cols:minmax(0,1.5fr) minmax(0,1fr)"><div><div class="card tbl-wrap"><table class="tbl"><thead><tr><th>Version</th><th>Data date</th><th>Finish</th><th>After changes</th><th>Activities</th></tr></thead><tbody>' + (vrows || '<tr><td colspan="5">No schedule yet.</td></tr>') + '</tbody></table></div>' +
          '<div class="acts" style="margin-top:12px"><button class="btn" data-schadd="1">Add an update</button><span class="fine">P6 .xer, Microsoft Project .xml, Excel or CSV. Each update can name the changes it absorbs.</span></div>' +
          '<div class="card tbl-wrap" style="margin-top:16px"><table class="tbl"><thead><tr><th>Change with time</th><th class="r">Days claimed</th><th>Status</th></tr></thead><tbody>' + (timed.map(function (c) { return '<tr data-copen="' + c.id + '"><td><span class="t">' + esc(c.title) + '</span><span class="id">' + esc(c.number) + '</span></td><td class="r">' + c.days + '</td><td>' + badge(c.status, c) + '</td></tr>'; }).join('') || '<tr><td colspan="3">None you can see.</td></tr>') + '</tbody></table></div></div>' +
          '<div>' + money2 + '<div class="card sec" style="margin-top:16px"><p class="fine" style="margin:0">A delay is paid only if the change’s work is on the critical path (' + esc(primeClause('extension_requires_critical_path') || 'see the contract') + '). Open a change with days claimed to analyze it against the latest version.</p></div></div></div>');
      }).catch(fail);
    });
  };

  /* ---------- 05 Activity (W6) ---------- */
  V.activity = function () {
    gate(function (C) {
      Promise.all([loadEvents(), q(P.sb().from('changes').select('*').eq('project_id', C.project.id)), loadPeople()]).then(function (r) {
        var byId = {}; r[1].forEach(function (c) { byId[c.id] = c; });
        var F = store('cs_actf') || {}, evs = r[0].filter(function (e) { return P.sees.event(e, byId); });
        var rows = evs.filter(function (e) { return (!F.co || e.company_id === F.co) && (!F.ai || e.ai) && (!F.ch || (byId[e.change_id] && byId[e.change_id].number.toLowerCase().indexOf(F.ch.toLowerCase()) >= 0)); }).reverse();
        var cos = Object.keys(C.companies);
        app.innerHTML = sheet('05 Activity', 'Activity log', '<p style="margin:-6px 0 14px;color:var(--muted)">Every action ' + esc(name(me())) + ' may see, newest first. Nothing here can be edited or deleted.</p>' +
          '<div class="grid filt" style="grid-template-columns:repeat(4,minmax(0,1fr)) auto;align-items:end;gap:10px"><div class="fd"><label><span>Company</span></label><div class="inp sel"><select id="fco"><option value="">All</option>' + cos.map(function (id) { return '<option value="' + id + '"' + (F.co === id ? ' selected' : '') + '>' + esc(name(id)) + '</option>'; }).join('') + '</select></div></div>' +
          '<div class="fd"><label><span>Change</span></label><div class="inp"><input id="fch" value="' + esc(F.ch || '') + '" placeholder="e.g. CP-0212"></div></div><div class="fd"><label class="tog-row"><input type="checkbox" id="fai"' + (F.ai ? ' checked' : '') + '> AI steps only</label></div><div></div><button class="btn" data-actexport="1">Export CSV</button></div>' +
          '<div class="card tbl-wrap" style="margin-top:14px"><table class="tbl"><thead><tr><th>When</th><th>Company</th><th>Action</th><th>Change</th><th>AI</th><th>Detail</th></tr></thead><tbody>' + rows.slice(0, 400).map(function (e) {
            var c = byId[e.change_id];
            return '<tr><td class="fine" style="white-space:nowrap">' + when(e.created_at) + '</td><td>' + esc(name(e.company_id)) + (e.actor && people[e.actor] ? '<span class="id">' + esc(people[e.actor].email) + '</span>' : '') + '</td><td>' + esc(KIND[e.kind] || e.kind) + (e.reason ? ' <span class="tagr chk">' + esc(REASON[e.reason] || e.reason) + '</span>' : '') + '</td><td>' + (c ? '<button class="link" data-copen="' + c.id + '">' + esc(c.number) + '</button>' : '—') + '</td><td>' + (e.ai ? esc(e.ai.model) + '<span class="id">' + (e.ai.citations || []).length + ' citations' + (e.ai.edited ? ', edited' : '') + (e.ai.rejected ? ', rejected' : '') + '</span>' : '—') + '</td><td class="fine">' + esc((e.body || '').slice(0, 140)) + '</td></tr>';
          }).join('') + '</tbody></table></div>' + (rows.length > 400 ? '<p class="fine">Showing the newest 400 of ' + rows.length + '. Export for all of them.</p>' : ''));
        V._actRows = { rows: rows, byId: byId };
      }).catch(fail);
    });
  };
  function exportActivity() {
    var X = V._actRows; if (!X) return;
    var cell = function (s) { s = String(s == null ? '' : s); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    var lines = [['time', 'company', 'person', 'action', 'reason', 'change', 'ai_model', 'ai_citations', 'ai_edited', 'detail'].join(',')].concat(X.rows.map(function (e) {
      var c = X.byId[e.change_id];
      return [e.created_at, name(e.company_id), e.actor && people[e.actor] ? people[e.actor].email : '', KIND[e.kind] || e.kind, e.reason || '', c ? c.number : '', e.ai ? e.ai.model : '', e.ai ? (e.ai.citations || []).join('; ') : '', e.ai ? !!e.ai.edited : '', e.body || ''].map(cell).join(',');
    }));
    var blob = new Blob([lines.join('\n') + '\n'], { type: 'text/csv' }), a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'clausestream-activity.csv'; document.body.appendChild(a); a.click(); a.remove();
  }

  /* ---------- 06 Project (W8): projects, companies, people, field links, connectors, data and AI ---------- */
  V.project = function () {
    P.connect().then(function () {
      var cfg = P.cfg();
      if (!cfg || !cfg.configured) return gate(function () {});
      if (!P.user()) return signIn();
      if (!ctx()) return projectList();
      projectSettings();
    }).catch(fail);
  };
  function projectList() {
    var sb = P.sb();
    q(sb.from('projects').select('*').order('created_at', { ascending: false })).then(function (ps) {
      app.innerHTML = sheet('06 Project', 'Your projects', '<p style="margin:-6px 0 18px;color:var(--muted)">Signed in as <b>' + esc(P.user().email) + '</b>. <button class="link" data-signout="1">Sign out</button></p>' +
        '<div class="cols" style="--cols:minmax(0,1.3fr) minmax(0,1fr)"><div class="card tbl-wrap">' + (ps.length ? '<table class="tbl"><thead><tr><th>Project</th><th>Type</th><th></th></tr></thead><tbody>' + ps.map(function (p) { return '<tr><td><span class="t">' + esc(p.name) + '</span><span class="id">' + (p.synthetic ? 'Synthetic' : 'Project') + '</span></td><td>' + esc(P.TYPE[p.contract_type] || '') + '</td><td><button class="btn sm" data-popen="' + p.id + '">Open</button></td></tr>'; }).join('') + '</tbody></table>' : '<p style="padding:18px;margin:0">No projects yet. Start one, or load the synthetic sample into your account. Invites appear here after you sign in with the invited email.</p>') + '</div>' +
        '<div class="card sec"><div class="sec-h"><h3>Start a project</h3></div><form id="newp" class="grid"><div class="fd full"><label><span>Project name</span></label><div class="inp"><input id="pname" required placeholder="e.g. Juanita HS modernization"></div></div>' +
        '<div class="fd"><label><span>Contract type</span></label><div class="inp sel"><select id="ptype">' + Object.keys(P.TYPE).map(function (k) { return '<option value="' + k + '">' + P.TYPE[k] + '</option>'; }).join('') + '</select></div></div>' +
        '<div class="fd"><label><span>Your company is the</span></label><div class="inp sel"><select id="prole">' + ['gc', 'owner', 'architect', 'sub'].map(function (k) { return '<option value="' + k + '">' + P.ROLE[k] + '</option>'; }).join('') + '</select></div></div>' +
        '<div class="fd full"><label><span>Your company’s name</span></label><div class="inp"><input id="pco" required placeholder="e.g. Cascade Builders"></div></div>' +
        '<div class="fd full"><button class="btn primary" type="submit">Start the project</button> <button class="btn" type="button" data-loadsample="1">Load the synthetic sample into my account</button></div></form></div></div>');
    }).catch(fail);
  }
  function projectSettings() {
    var C = ctx(), sb = P.sb();
    Promise.all([loadPeople(), C.admin && !P.isSample() ? q(sb.from('invites').select('*').eq('project_id', C.project.id)).catch(function () { return []; }) : Promise.resolve([]),
      q(sb.from('field_links').select('*').eq('project_id', C.project.id)).catch(function () { return []; })]).then(function (r) {
      var ppl = r[0], inv = r[1], links = r[2].filter(function (l) { return l.company_id === me() || (C.admin && P.isSample()); });
      var byRole = ['owner', 'architect', 'gc', 'sub'].map(function (g) { var ids = P.byRole(g); return ids.length ? '<li><b>' + P.ROLE[g] + (g === 'sub' && ids.length > 1 ? 's' : '') + '</b> ' + ids.map(function (id) { return esc(name(id)) + (C.companies[id].trade ? ' <span class="fine">(' + esc(C.companies[id].trade) + ')</span>' : ''); }).join(', ') + '</li>' : ''; }).join('');
      var linkUrl = function (l) { return P.isSample() ? location.origin + location.pathname + '#field?t=' + l.token : location.origin + '/app/field/?t=' + l.token; };
      var lk = links.map(function (l) { return '<li><b>' + esc(name(l.company_id)) + '</b> ' + (l.active ? '<span class="badge ok">on</span>' : '<span class="badge">off</span>') + '<div class="fine" style="word-break:break-all">' + esc(linkUrl(l)) + '</div><div class="acts" style="margin-top:6px"><button class="btn ghost sm" data-fcopy="' + esc(linkUrl(l)) + '">Copy link</button>' + (P.isSample() ? '<a class="btn ghost sm" href="#field?t=' + esc(l.token) + '">Open it (sample)</a>' : '') + (l.active ? '<button class="btn ghost sm" data-foff="' + esc(l.token) + '">Turn off</button>' : '') + '</div></li>'; }).join('');
      app.innerHTML = sheet('06 Project', C.project.name, '<p style="margin:-6px 0 18px;color:var(--muted)">' + esc(P.TYPE[C.project.contract_type] || '') + (C.project.synthetic ? ' · synthetic' : '') + '. ' + (P.isSample() ? '<button class="link" data-leavesample="1">Leave the sample</button>' : 'Signed in as <b>' + esc(P.user().email) + '</b>. <button class="link" data-pclose="1">Switch project</button> · <button class="link" data-signout="1">Sign out</button>') + '</p>' +
        '<div class="cols" style="--cols:minmax(0,1fr) minmax(0,1fr)"><div><div class="card sec"><div class="sec-h"><h3>Companies on the project</h3></div><ul class="plain">' + byRole + '</ul>' +
        (C.admin ? '<div class="fd" style="margin-top:12px;max-width:320px"><label><span>Contract type</span></label><div class="inp sel"><select id="ptype2">' + Object.keys(P.TYPE).map(function (k) { return '<option value="' + k + '"' + (k === C.project.contract_type ? ' selected' : '') + '>' + P.TYPE[k] + '</option>'; }).join('') + '</select></div></div><p class="fine">Hard bid projects see more delay claims, so the delay steps lead there.</p>' : '') + '</div>' +
        '<div class="card sec" style="margin-top:16px"><div class="sec-h"><h3>People</h3></div><ul class="plain">' + ppl.filter(function (p, i, a) { return a.findIndex(function (x) { return x.user_id === p.user_id && x.company_id === p.company_id; }) === i; }).map(function (p) { return '<li>' + esc(p.email) + ' <span class="fine">' + esc(p.company) + ' · ' + esc(P.ROLE[p.role]) + '</span></li>'; }).join('') + inv.map(function (i) { return '<li>' + esc(i.email) + ' <span class="fine">' + esc(i.company_name) + ' · ' + esc(P.ROLE[i.role]) + ' · invited</span></li>'; }).join('') + '</ul>' +
        (C.admin && !P.isSample() ? '<form id="inv" class="grid" style="margin-top:12px"><div class="fd"><label><span>Invite by email</span></label><div class="inp"><input id="iemail" type="email" required placeholder="pm@firm.com"></div></div><div class="fd"><label><span>Their company</span></label><div class="inp"><input id="icompany" required></div></div><div class="fd"><label><span>As the</span></label><div class="inp sel"><select id="irole">' +
          ['owner', 'architect', 'gc', 'sub'].map(function (k) { return '<option value="' + k + '">' + P.ROLE[k] + '</option>'; }).join('') + '</select></div></div><div class="fd full"><button class="btn sm" type="submit">Invite</button><span class="fine" style="margin-left:10px">They join when they sign in with that email.</span></div></form>' : '') + '</div></div>' +
        '<div><div class="card sec"><div class="sec-h"><h3>Field links</h3><span class="fine">no account</span></div><p class="fine" style="margin:0 0 10px">One link per sub. A foreman types what happened and adds photos; it arrives in that sub’s inbox, unverified. The link can add, never read.</p>' + (lk ? '<ul class="plain">' + lk + '</ul>' : (role() === 'sub' ? '<button class="btn sm" data-fnew="1">Make a field link</button>' : '<p class="fine" style="margin:0">Each sub makes its own.</p>')) + '</div>' +
        '<div class="card sec" style="margin-top:16px"><div class="sec-h"><h3>Connectors</h3></div><ul class="plain"><li><b>Procore</b> <span class="tagr none">not connected</span> <span class="fine">RFIs and change orders in, read-only first; results written back later.</span></li><li><b>Newforma, the owner’s system</b> <span class="tagr none">planned</span></li></ul></div>' +
        '<div class="card sec" style="margin-top:16px"><div class="sec-h"><h3>Data and AI</h3></div><ul class="plain"><li>AI runs on a free open model on your own machine, or as a saved test run online. Nothing goes to outside AI services.</li><li>The AI may cite only entries in the record; code checks every citation and computes every number.</li><li>Every AI step is logged with its model, citations and who accepted or changed it (05 Activity).</li></ul></div></div></div>');
      var t2 = document.getElementById('ptype2'); if (t2) t2.onchange = function () { q(sb.from('projects').update({ contract_type: t2.value }).eq('id', C.project.id)).then(function () { C.project.contract_type = t2.value; A.toast('Contract type saved.'); }).catch(fail); };
      var f = document.getElementById('inv');
      if (f) f.addEventListener('submit', function (e) { e.preventDefault(); q(sb.from('invites').insert({ project_id: C.project.id, email: document.getElementById('iemail').value.trim().toLowerCase(), company_name: document.getElementById('icompany').value.trim(), role: document.getElementById('irole').value })).then(function () { A.toast('Invited.'); projectSettings(); }).catch(fail); });
    }).catch(fail);
  }

  /* ---------- the field link page (in the sample; the live one is /app/field/) ---------- */
  V.field = function () {
    var token = (location.hash.split('t=')[1] || '').split('&')[0];
    P.connect().then(function () {
      return q(P.sb().rpc('field_link_info', { p_token: token }));
    }).then(function (info) { V.fieldForm(app, info && info[0], function (body, nm, files) { return q(P.sb().rpc('submit_field', { p_token: token, p_body: body, p_name: nm, p_photos: (files || []).map(function (f) { return URL.createObjectURL(f); }) })); }); }).catch(fail);
  };
  V.fieldForm = function (el, info, send) {
    if (!info) { el.innerHTML = '<div class="wrap phone"><div class="card sec"><h2>This link isn’t active</h2><p class="fine">Ask your project manager for a new one.</p></div></div>'; return; }
    el.innerHTML = '<div class="wrap phone"><div class="card sec"><span class="eyebrow">' + esc(info.project) + '</span><h2 style="margin:6px 0 2px">' + esc(info.company) + '</h2><p class="fine" style="margin:0 0 14px">Tell your PM what happened. It goes to ' + esc(info.company) + ' only, unverified until they confirm it.</p>' +
      '<form id="ff"><div class="fd"><label><span>What happened?</span></label><div class="inp" style="height:auto"><textarea id="fbody" rows="6" required minlength="3" placeholder="e.g. Found old pipe in the wall at room 112, can\'t run new line until someone decides"></textarea></div></div>' +
      '<div class="fd" style="margin-top:10px"><label><span>Photos (optional, up to 4)</span></label><input id="fphotos" type="file" accept="image/*" multiple></div>' +
      '<div class="fd" style="margin-top:10px"><label><span>Your name</span></label><div class="inp"><input id="fname" autocomplete="name"></div></div>' +
      '<button class="btn primary" type="submit" style="margin-top:14px;width:100%">Send to ' + esc(info.company) + '</button></form><p class="fine" style="margin:12px 0 0">Typing and photos. Your phone keyboard’s own dictation works too.</p></div></div>';
    document.getElementById('ff').addEventListener('submit', function (e) {
      e.preventDefault(); var b = e.target.querySelector('button'); b.disabled = true;
      var files = [].slice.call(document.getElementById('fphotos').files || []).filter(function (f) { return /^image\//.test(f.type) && f.size < 10e6; }).slice(0, 4);
      send(document.getElementById('fbody').value.trim(), document.getElementById('fname').value.trim(), files).then(function () {
        el.innerHTML = '<div class="wrap phone"><div class="card sec"><h2>Sent</h2><p>' + esc(info.company) + ' will see it in their inbox.</p><button class="btn" onclick="location.reload()">Send another</button></div></div>';
      }).catch(function (er) { b.disabled = false; fail(er); });
    });
  };

  /* ---------- clicks and forms ---------- */
  app.addEventListener('click', function (e) {
    var t = e.target.closest('[data-copen],[data-dopen],[data-chf],[data-tact],[data-tbundle],[data-tbundleall],[data-tnotice],[data-tdraft],[data-tconfirm],[data-tcheck],[data-texplain],[data-tdelay],[data-receipt],[data-ksel],[data-tconf],[data-schadd],[data-actexport],[data-popen],[data-pclose],[data-signout],[data-loadsample],[data-entersample],[data-leavesample],[data-fconfirm],[data-fdiscard],[data-fnew],[data-foff],[data-fcopy]');
    if (!t) return;
    var d = t.dataset;
    if (d.copen) { store('cs_change', d.copen); return A.go('change'); }
    if (d.dopen) { store('cs_doc', d.dopen); return A.go('doc'); }
    if (d.chf) { store('cs_chfilter', d.chf); return V.changes(); }
    if (d.entersample) { e.preventDefault(); return P.enterSample('home'); }
    if (d.leavesample) { e.preventDefault(); return P.leaveSample(); }
    if (d.signout) { return P.sb().auth.signOut().then(function () { store('cs_project', null); location.reload(); }); }
    if (d.pclose) { P.closeProject(); return V.project(); }
    if (d.popen) { return P.openProject(d.popen).then(function () { A.go('home'); }).catch(fail); }
    if (d.loadsample) { e.preventDefault(); app.innerHTML = '<div class="wrap"><div class="reading"><div class="spinner"></div><h2>Loading the synthetic sample into your account</h2><p class="fine" id="prog">Starting…</p></div></div>';
      return P.seedSample(P.sb(), function (w) { var el = document.getElementById('prog'); if (el) el.textContent = 'Saving ' + w + '…'; }).then(function (pid) { return P.openProject(pid); }).then(function () { A.toast('Sample loaded. Use “Viewing as” to act as each company.'); A.go('home'); }).catch(function (er) { fail(er); V.project(); }); }
    if (d.receipt) return showReceipt(d.receipt);
    if (d.ksel) { store('cs_contract_sel', d.ksel); return V.contracts(); }
    if (d.tconf) return q(P.sb().from('contract_terms').update({ confirmed_by: P.user().id, confirmed_at: new Date().toISOString() }).eq('id', d.tconf)).then(function () { return P.loadCtx(ctx().project.id); }).then(function () { A.toast('Confirmed.'); V.contracts(); }).catch(fail);
    if (d.schadd) { store('cs_sched_target', 'project'); return A.go('schedule-load'); }
    if (d.actexport) return exportActivity();
    if (d.fcopy) { (navigator.clipboard ? navigator.clipboard.writeText(d.fcopy) : Promise.reject()).then(function () { A.toast('Link copied.'); }, function () { window.prompt('Copy this link:', d.fcopy); }); return; }
    if (d.fnew) return q(P.sb().from('field_links').insert({ project_id: ctx().project.id, company_id: me() })).then(projectSettings).catch(fail);
    if (d.foff) return q(P.sb().from('field_links').update({ active: false }).eq('token', d.foff)).then(projectSettings).catch(fail);
    if (d.fdiscard) return q(P.sb().from('field_submissions').update({ status: 'discarded' }).eq('id', d.fdiscard)).then(V.home).catch(fail);
    if (d.fconfirm) {
      var sb = P.sb(), C = ctx();
      return q(sb.from('field_submissions').select('*').eq('id', d.fconfirm).single()).then(function (s) {
        var k = P.subcontractOf(me());
        return loadChanges().then(function (ch) {
          var n = ch.reduce(function (m, c) { var x = parseInt(String(c.number).replace(/\D/g, ''), 10); return String(c.number).indexOf('CR-') === 0 && isFinite(x) && x > m ? x : m; }, 100) + 1;
          return q(sb.from('changes').insert({ project_id: C.project.id, number: 'CR-' + ('0000' + n).slice(-4), title: s.body.split(/[.\n]/)[0].slice(0, 80), tier: 'sub_request', contract_id: k ? k.id : null, from_company: me(), to_company: k ? k.up_company : P.byRole('gc')[0], cause: { type: 'Other event', event_date: s.created_at.slice(0, 10) }, meta: { field_submission: s.id, raised_in_app: true, photos: s.photos || [] } }).select().single());
        }).then(function (c) {
          return q(sb.from('events').insert({ project_id: C.project.id, change_id: c.id, company_id: me(), kind: 'note', body: 'From the field' + (s.sender_name ? ' (' + s.sender_name + ')' : '') + ': ' + s.body })).then(function () {
            return q(sb.from('field_submissions').update({ status: 'confirmed', change_id: c.id }).eq('id', s.id));
          }).then(function () { store('cs_change', c.id); A.go('change'); });
        });
      }).catch(fail);
    }
    if (!T) return;
    if (d.tbundle !== undefined) {
      var target = d.tbundle;
      return q(P.sb().from('changes').select('*').eq('project_id', T.c.project_id).eq('number', target)).then(function (rows) {
        var prop = rows[0]; if (!prop) throw new Error('No proposal ' + (target || '') + ' yet. Raise one in 01 Changes, then put this request in it.');
        return bundle([T.c], prop);
      }).then(function () { A.toast('Put in ' + target + '.'); V.change(); }).catch(fail);
    }
    if (d.tbundleall) return bundle(T.waiting, T.c).then(function () { A.toast('Sub requests added.'); V.change(); }).catch(fail);
    if (d.tnotice) return modal('Notice of potential change', 'Step 1 · ' + T.c.number, '<pre class="draft">' + esc(noticeText(T.c)) + '</pre><p class="fine">Drafted by code from ' + esc((noticeDays(T.c) || {}).clause || 'the contract') + '. Sending it is logged with today’s date.</p>', [['Send the notice', 'primary', function () { return post('notice', { body: noticeText(T.c), payload: { built_by: 'code', clause: (noticeDays(T.c) || {}).clause } }); }]]);
    if (d.tdraft) return draftStep();
    if (d.tconfirm) return confirmModal();
    if (d.tcheck) return runChecks().then(function () { A.toast('Checks saved to the activity log.'); V.change(); }).catch(fail);
    if (d.texplain) { var tx = document.getElementById('texplain').value.trim(); if (!tx) return A.toast('Write what you changed, or why it stands.'); return post('explain', { body: tx }).then(function () { V.change(); }).catch(fail); }
    if (d.tdelay) return startDelay();
    if (d.tact) {
      var k2 = d.tact, box = document.getElementById('reasonbox'), b = document.getElementById('tbody');
      if (k2 === 'return' && box && box.hidden) { box.hidden = false; t.textContent = 'Confirm return'; return; }
      if (k2 === 'comment' && !(b && b.value.trim())) return A.toast('Write a comment first.');
      var extra = {};
      if (k2 === 'return') extra.reason = document.getElementById('treason').value;
      var pre = Promise.resolve();
      if (k2 === 'submit' && T.c.tier === 'sub_request' && document.getElementById('tamount')) pre = q(P.sb().from('changes').update({ amount: A.num(document.getElementById('tamount').value), days: Math.round(A.num(document.getElementById('tdays').value)) }).eq('id', T.c.id));
      return pre.then(function () { return post(k2, extra); }).then(function () { A.toast(k2 === 'submit' ? 'Sent.' : k2 === 'return' ? 'Returned with a reason.' : k2 === 'approve' ? 'Approved.' : k2 === 'forward' ? 'Forwarded.' : 'Saved.'); V.change(); }).catch(fail);
    }
  });
  app.addEventListener('submit', function (e) {
    var id = e.target.id;
    if (id === 'rsearch') { e.preventDefault(); var v = document.getElementById('rq').value.trim(); store('cs_rq', v); if (v) search(v); return; }
    if (id === 'rup') { e.preventDefault(); return upload(); }
    if (id === 'newp') {
      e.preventDefault();
      return q(P.sb().rpc('start_project', { p_name: document.getElementById('pname').value.trim(), p_type: document.getElementById('ptype').value, p_company: document.getElementById('pco').value.trim(), p_role: document.getElementById('prole').value, p_synthetic: false }))
        .then(function (pid) { return P.openProject(pid); }).then(function () { A.toast('Project started. Invite the other companies in 06 Project.'); A.go('project'); }).catch(fail);
    }
  });
  app.addEventListener('change', function (e) {
    var t = e.target; if (!/^(fco|fch|fai)$/.test(t.id)) return;
    store('cs_actf', { co: document.getElementById('fco').value || null, ch: document.getElementById('fch').value.trim() || null, ai: document.getElementById('fai').checked });
    V.activity();
  });
  // The band lives outside the sheet.
  document.addEventListener('click', function (e) {
    var t = e.target.closest('#modeband [data-leavesample],#modeband [data-entersample]'); if (!t) return;
    if (t.dataset.leavesample) P.leaveSample(); else P.enterSample('home');
  });
  // ?project=sample (the landing page's link) opens the sample directly.
  if (/[?&]project=sample/.test(location.search)) { store('cs_mode', 'sample'); history.replaceState(null, '', location.pathname + (location.hash || '#home')); }
  // ?mode=live (the landing page's Sign in link) leaves the sample and shows sign-in.
  if (/[?&]mode=live/.test(location.search)) { store('cs_mode', 'live'); history.replaceState(null, '', location.pathname + (location.hash || '#home')); }
  P.connect().then(function () { P.band(); }).catch(function () {});
})();
