/* Getting started: the welcome screen (#start) and the guide panel.
   A new person picks "try the sample" or "start a real project", then (for the sample) which party they are.
   Each guide step ticks off when the person really does it: the guide reads the project's data and the screen,
   it never takes the action for them. State is kept in this browser (cs_guide). */
(function () {
  'use strict';
  var A = window.CSApp, P = window.CSPlat, esc = A.esc, store = A.store, app = A.app;
  var V = window.CSViews = window.CSViews || {};
  var q = P.q;

  /* ---------- small helpers the steps use ---------- */
  function view() { return (location.hash || '#home').slice(1).split('?')[0] || 'home'; }
  function ctx() { return P.ctx(); }
  function myRole() { return ctx() ? P.myRole() : null; }
  function onChange(num) { return view() === 'change' && document.body.dataset.change === num; }
  function changeBy(num) {
    if (!ctx()) return Promise.resolve(null);
    return q(P.sb().from('changes').select('*').eq('project_id', ctx().project.id).eq('number', num)).then(function (r) { return r[0] || null; });
  }
  function kinds(num) {
    return changeBy(num).then(function (c) {
      if (!c) return {};
      return q(P.sb().from('events').select('kind,payload').eq('change_id', c.id)).then(function (es) { var o = {}; es.forEach(function (e) { o[e.kind] = (o[e.kind] || []).concat([e]); }); return o; });
    });
  }
  function status(num) { return changeBy(num).then(function (c) { return c ? c.status : null; }); }
  function companyFor(role) {
    var C = ctx(); if (!C) return null;
    if (role === 'sub') return Object.keys(C.companies).filter(function (id) { return /clearwater/i.test(C.companies[id].name); })[0] || P.byRole('sub')[0];
    return P.byRole(role)[0];
  }
  // The change the sub's crew note became (the newest field change request from the viewer's company).
  function fieldChange() {
    if (!ctx()) return Promise.resolve(null);
    return q(P.sb().from('changes').select('*').eq('project_id', ctx().project.id).eq('from_company', ctx().viewAs)).then(function (cs) {
      return cs.filter(function (c) { return (c.meta || {}).field_submission; }).sort(function (a, b) { return a.number < b.number ? 1 : -1; })[0] || null;
    });
  }
  function rowFor(num) { return function () { return [].slice.call(document.querySelectorAll('[data-copen]')).filter(function (el) { return el.textContent.indexOf(num) >= 0; })[0]; }; }
  function cardWith(sel) { return function () { var el = document.querySelector(sel); return el && (el.closest('.card') || el); }; }

  var ROLE_TEXT = { sub: 'Subcontractor', gc: 'GC/CM', architect: 'Architect', owner: 'Owner’s rep' };

  /* ---------- the sample guides, one per party ---------- */
  // Step fields: title, text, why, target (selector or function), open (a change number to jump to), go (a view),
  // ack (done when the person clicks "Got it"), check (done when it returns true, or a promise of true).
  var SAMPLE = {
    gc: [
      { title: 'This is Home', text: 'Home lists what’s waiting on you, and the clocks the contracts set for notice, pricing and review. A red clock is late.', target: '.card.tbl-wrap', go: 'home', ack: true },
      { title: 'Open CP-0212', text: 'Click the row for CP-0212, extra haul-off for abatement debris.', target: rowFor('CP-0212'), go: 'home', check: function () { return onChange('CP-0212'); } },
      { title: 'Add the sub’s price', text: 'Clearwater Abatement sent its price for this work. Click “Put the 1 waiting request in”.', why: 'Each sub prices its own work. You collect their requests into one proposal, and code checks that they add up.',
        target: '[data-tbundleall]', open: 'CP-0212', check: function () { return changeBy('CP-0212').then(function (c) { return c ? q(P.sb().from('changes').select('id').eq('parent_id', c.id)).then(function (k) { return k.length > 0; }) : false; }); } },
      { title: 'Let the AI draft it', text: 'Click “Draft it”. Open a citation to see the exact source, then click Accept.', why: 'The AI may only cite what’s in the project record, and code checks every citation is real.',
        target: '[data-tdraft]', open: 'CP-0212', check: function () { return kinds('CP-0212').then(function (k) { return !!k.draft; }); } },
      { title: 'Confirm the numbers', text: 'Click “Review and confirm”, look over the amounts, and confirm them.', why: 'The checks only use numbers a person has confirmed.',
        target: '[data-tconfirm]', open: 'CP-0212', check: function () { return kinds('CP-0212').then(function (k) { return !!k.confirm; }); } },
      { title: 'Run the contract checks', text: 'Click “Run the checks”.', why: 'Code checks markups, the fee and the deadlines against the prime contract. No AI in this step.',
        target: '[data-tcheck]', open: 'CP-0212', check: function () { return kinds('CP-0212').then(function (k) { return !!k.check; }); } },
      { title: 'Explain the finding', text: 'The checks found a fee charged on items the contract excludes ($210). Type what you’d change, or why it stands, and click “Save the explanation”.', why: 'You can’t send a proposal with an open finding. The architect sees your note.',
        target: '#texplain', open: 'CP-0212', check: function () { return kinds('CP-0212').then(function (k) { var last = (k.check || []).slice(-1)[0]; return !!k.explain || (last && !+((last.payload || {}).findings || 0)); }); } },
      { title: 'Send it to the architect', text: 'Click “Send to Example Architecture, PLLC”.', target: '[data-tact="submit"]', open: 'CP-0212',
        check: function () { return status('CP-0212').then(function (s) { return s && s !== 'draft' && s !== 'returned'; }); } },
      { title: 'See the hand-off', text: 'In the band at the top, switch “Viewing as” to Example Architecture, PLLC. CP-0212 is now waiting on them, with a review clock.', target: '#viewas', check: function () { return myRole() === 'architect'; } }
    ],
    sub: [
      { title: 'A note from your crew', text: 'Your foreman sent this from the field link on a phone, no account needed. It’s unverified: only your company can see it.', why: 'Nothing from the field reaches the GC/CM until you confirm it.', target: cardWith('[data-fconfirm]'), go: 'home', ack: true },
      { title: 'Make it a change request', text: 'Click “Make it a change request” on the note about the black mastic.', target: '[data-fconfirm]', go: 'home', check: function () { return fieldChange().then(function (c) { return !!c; }); } },
      { title: 'Send it to the GC/CM', text: 'Enter your price if you have one, add a note, and click “Send to Example Builders, Inc.”.', why: 'Once sent, the GC/CM sees it and its pricing clock starts.',
        target: '[data-tact="submit"]', openFn: fieldChange, check: function () { return fieldChange().then(function (c) { return c && c.status !== 'draft'; }); } },
      { title: 'What you can see', text: 'Open 01 Changes. You see your own requests, not the GC/CM’s proposal to the owner or other subs’ prices.', why: 'Who sees what follows the contracts: you’re party to your subcontract only.', target: '[data-nav="changes"]', go: 'changes', ack: true },
      { title: 'See the hand-off', text: 'Switch “Viewing as” at the top to Example Builders, Inc. Your request is waiting on them.', target: '#viewas', check: function () { return myRole() === 'gc'; } }
    ],
    architect: [
      { title: 'Late reviews show in red', text: 'The contract gives you 14 days to review a proposal (§ 6.4). The clocks on Home count them, and red ones are late.', target: '.clocks', go: 'home', ack: true },
      { title: 'Open CP-0220', text: 'Click CP-0220, the proposal waiting on you.', target: rowFor('CP-0220'), go: 'home', check: function () { return onChange('CP-0220'); } },
      { title: 'Read what the GC/CM sent', text: 'The evidence on the right shows what caused the change, each item linked to the record. Under “Activity on this change” are the checks the GC/CM ran and their notes.', target: '#tevidence', open: 'CP-0220', ack: true },
      { title: 'Forward it or send it back', text: 'Click “Forward to” the owner, or “Return” it with a reason. Either way it’s logged.', target: '[data-tact="forward"]', open: 'CP-0220',
        check: function () { return status('CP-0220').then(function (s) { return s && s !== 'with_architect'; }); } },
      { title: 'See the hand-off', text: 'Switch “Viewing as” at the top to Example School District No. 1 to see what the owner gets.', target: '#viewas', check: function () { return myRole() === 'owner'; } }
    ],
    owner: [
      { title: 'This is Home', text: 'Proposals reach you after the architect reviews them. Each shows its review clock from the contract.', target: '.card.tbl-wrap', go: 'home', ack: true },
      { title: 'Open CP-0230', text: 'Click CP-0230, the proposal waiting on your decision.', target: rowFor('CP-0230'), go: 'home', check: function () { return onChange('CP-0230'); } },
      { title: 'See what’s inside', text: 'You see the proposal and a summary of the sub requests in it, not each sub’s own pricing. That stays between each sub and the GC/CM.', target: '#tlinked', open: 'CP-0230', ack: true },
      { title: 'Decide', text: 'Click Approve, Reject, or Return to the architect. An approval flows down to the sub requests inside it.', target: '[data-tact="approve"]', open: 'CP-0230',
        check: function () { return status('CP-0230').then(function (s) { return s && s !== 'with_owner'; }); } },
      { title: 'Check the record', text: 'Open 05 Activity. Every action is there, permanent. Steps that used AI have a receipt: the model, its citations, and who accepted it.', target: '[data-nav="activity"]', check: function () { return view() === 'activity'; } }
    ]
  };

  /* ---------- the real-project checklist ---------- */
  function realSteps() {
    var C = ctx(), r = myRole(), admin = C && C.admin, out = [
      { title: 'Sign in', text: 'Enter your work email. We send a one-time link; there’s no password.', go: 'home', target: '#email', check: function () { return !!P.user() && !P.isSample(); } },
      { title: 'Start or open your project', text: 'On 06 Project, name the project and pick the contract type and your company’s role. If someone invited you, the project is already in your list.', go: 'project', target: '#newp', check: function () { return !!ctx() && !P.isSample(); } }
    ];
    if (!C || admin) out.push(
      { title: 'Invite the other companies', text: 'On 06 Project, invite one person from each company: the owner’s rep, the architect, and your subs. Each joins when they sign in with that email.', go: 'project', target: '#inv',
        check: function () { if (!ctx()) return false; return Object.keys(ctx().companies).length > 1 || q(P.sb().from('invites').select('email').eq('project_id', ctx().project.id)).then(function (i) { return i.length > 0; }).catch(function () { return false; }); } },
      { title: 'Add a contract and read its terms', text: 'Once a company has joined, add the contract between you on 03 Contracts, then click “Read its terms”: upload the contract and confirm each term with the sentence it came from.', why: 'The checks and clocks run on confirmed terms only.', go: 'contracts', target: '#addk',
        check: function () { if (!ctx()) return false; return q(P.sb().from('contract_terms').select('id,confirmed_at').eq('project_id', ctx().project.id)).then(function (t) { return t.some(function (x) { return x.confirmed_at; }); }); } });
    if (r === 'sub') out.push({ title: 'Make a field link for your crew', text: 'On 06 Project, click “Make a field link” and send it to your foreman. They can send notes and photos from a phone without an account.', go: 'project', target: '[data-fnew]',
      check: function () { return q(P.sb().from('field_links').select('token').eq('company_id', ctx().viewAs)).then(function (l) { return l.length > 0; }); } });
    if (r === 'sub' || r === 'gc') out.push({ title: 'Raise your first change', text: 'On 01 Changes, describe what happened the way you’d say it on site, and click “Raise it”. The notice clock starts from the date it happened.', go: 'changes', target: '#newc',
      check: function () { return q(P.sb().from('changes').select('id').eq('project_id', ctx().project.id).eq('from_company', ctx().viewAs)).then(function (c) { return c.length > 0; }); } });
    if (r === 'architect' || r === 'owner') out.push({ title: 'Wait for the first proposal', text: 'Nothing else to set up. Proposals arrive on Home once the GC/CM sends them, each with a review clock from the contract.', go: 'home', ack: true });
    return out;
  }

  /* ---------- state ---------- */
  function S() { return store('cs_guide'); }
  function save(s) { store('cs_guide', s); }
  function steps(s) { return !s ? [] : s.path === 'real' ? realSteps() : SAMPLE[s.role] || []; }
  P.guide = { steps: steps, SAMPLE: SAMPLE };

  /* ---------- the welcome screen ---------- */
  V.start = function () {
    store('cs_seen_start', 1);
    var pick = /[?&]pick=role/.test(location.hash);
    var how = '<ul class="plain gs-how"><li><b>One record for every company.</b> RFIs, ASIs, submittals, approved minutes, contracts and changes, kept in one place.</li><li><b>You see what your contracts allow.</b> A sub sees its own work; the owner sees proposals, not each sub’s prices.</li><li><b>AI drafts, code checks, a person decides.</b> Every AI step cites the record and is logged.</li></ul>';
    var body = pick
      ? '<p class="lede gs-lede">The sample is a made-up school project with an owner, an architect, a GC/CM and 25 subcontractors. Pick who you are, and the guide walks you through that party’s part, then the hand-off to the next.</p>' +
        '<div class="gs-grid">' + [['sub', 'Turn your crew’s note from the field into a change request, and send it to the GC/CM.'], ['gc', 'Put a sub’s price into a proposal, draft it with AI, run the contract checks, and send it.'],
          ['architect', 'Review a proposal that’s overdue, and forward it to the owner or send it back.'], ['owner', 'Decide on a proposal, and see the full record of who did what.']].map(function (x) {
          return '<button class="gs-card" data-gsrole="' + x[0] + '"><b>' + ROLE_TEXT[x[0]] + '</b><span>' + x[1] + '</span><em>About 5 minutes</em></button>';
        }).join('') + '</div><p class="fine"><a class="link" href="#start">Back</a></p>'
      : '<p class="lede gs-lede">ClauseStream keeps one shared record for a construction project, from the subcontractors up to the owner, and checks each change against the contracts before it’s sent.</p>' + how +
        '<div class="gs-grid two"><button class="gs-card" data-gspath="sample"><b>Try the sample project</b><span>A made-up school project. No sign-in, and nothing you do is saved.</span><em>About 5 minutes</em></button>' +
        '<button class="gs-card" data-gspath="real"><b>Start a real project</b><span>Sign in with your email, set up your project, and invite the other companies.</span><em>About 10 minutes to set up</em></button></div>' +
        '<p class="fine">Just want to check one proposal against a contract? <a class="link" href="#upload">Use the quick check</a>.</p>';
    app.innerHTML = '<div class="wrap"><div class="ph1"><div><span class="eyebrow">Getting started</span><h1 style="margin-top:8px">' + (pick ? 'Which are you?' : 'What brings you here?') + '</h1></div></div>' + body + '</div>';
    hidePanel();
  };

  /* ---------- the panel ---------- */
  var panel = null, busy = 0, lastShown = -1, hidden = false;
  function ensurePanel() {
    if (panel) return panel;
    panel = document.createElement('aside'); panel.id = 'guide'; panel.className = 'guide'; panel.setAttribute('aria-label', 'Getting-started guide');
    document.body.appendChild(panel);
    panel.addEventListener('click', onPanelClick);
    return panel;
  }
  function hidePanel() { if (panel) panel.hidden = true; document.body.classList.remove('has-guide'); clearTarget(); }
  function clearTarget() { document.querySelectorAll('.g-target').forEach(function (el) { el.classList.remove('g-target'); }); }
  function targetOf(st) { if (!st || !st.target) return null; return typeof st.target === 'function' ? st.target() : document.querySelector(st.target); }

  function evaluate() {
    var s = S(); if (!s || view() === 'start') return hidePanel();
    // The sample guide opens on the party the person picked, once the sample has loaded.
    if (s.path === 'sample' && s.viewAs !== 'done' && ctx() && P.isSample()) {
      var co = companyFor(s.role); s.viewAs = 'done'; save(s);
      if (co && ctx().viewAs !== co) return P.setViewAs(co);
    }
    if (s.path === 'sample' && !P.isSample()) return hidePanel();
    var list = steps(s), my = ++busy;
    // Walk forward past every step already done; stop at the first that isn't.
    // A sample step, once done, stays done: later steps move the person on (another screen, another party).
    var i = s.path === 'real' ? 0 : Math.min(s.reached || 0, list.length), done = [];
    for (var k0 = 0; k0 < i; k0++) done[k0] = true;
    function next() {
      if (i >= list.length) return Promise.resolve();
      var st = list[i];
      var ok = st.ack ? Promise.resolve(!!(s.acked || {})[i]) : Promise.resolve().then(function () { return st.check(); }).catch(function () { return false; });
      return ok.then(function (v) { done[i] = !!v; if (v) { i++; return next(); } });
    }
    // The real-project checklist shows every step; it still stops at the first not done.
    function all() { return Promise.all(list.map(function (st, k) { return st.ack ? !!(s.acked || {})[k] : Promise.resolve().then(function () { return st.check(); }).catch(function () { return false; }); })); }
    (s.path === 'real' ? all().then(function (r) { done = r.map(Boolean); i = done.indexOf(false); if (i < 0) i = list.length; }) : next()).then(function () {
      if (my !== busy) return;
      if (s.path !== 'real' && i > (s.reached || 0)) { s = S() || s; s.reached = i; save(s); }
      draw(s, list, i, done);
    });
  }

  function draw(s, list, i, done) {
    ensurePanel(); panel.hidden = false; document.body.classList.toggle('has-guide', !s.min);
    clearTarget();
    var finished = i >= list.length, st = list[i];
    if (s.min) {
      panel.className = 'guide min';
      panel.innerHTML = '<button class="gd-open" data-gd="open">Guide' + (finished ? ': done' : ': step ' + (i + 1) + ' of ' + list.length) + '</button>';
      return;
    }
    panel.className = 'guide';
    var head = '<div class="gd-h"><span>' + (s.path === 'real' ? 'Set up your project' : 'Guide · ' + ROLE_TEXT[s.role]) + '</span><span class="gd-n">' + (finished ? 'Done' : 'Step ' + (i + 1) + ' of ' + list.length) + '</span><button class="gd-x" data-gd="min" aria-label="Hide the guide">Hide</button></div>';
    var bar = '<div class="gd-bar" aria-hidden="true">' + list.map(function (x, k) { return '<i class="' + (done[k] || k < i ? 'on' : k === i ? 'now' : '') + '"></i>'; }).join('') + '</div>';
    var body;
    if (finished) {
      body = s.path === 'real'
        ? '<h3 aria-live="polite">You’re set up</h3><p>Your project is ready. Changes and proposals will show on Home as they arrive.</p><div class="gd-acts"><button class="btn sm primary" data-gd="close">Close the guide</button></div>'
        : '<h3 aria-live="polite">That’s the ' + esc(ROLE_TEXT[s.role]) + ' side</h3><p>Each party worked from the same record and saw only what its contracts allow. Every step is in 05 Activity.</p>' +
          '<div class="gd-acts"><a class="btn sm primary" href="#start?pick=role" data-gd="again">Try another party</a><button class="btn sm" data-gd="real">Start a real project</button><button class="btn sm ghost" data-gd="close">Close</button></div>';
    } else {
      var here = st.open ? onChange(st.open) : st.openFn ? view() === 'change' : st.go ? view() === st.go : true;
      var tgt = targetOf(st);
      var goBtn = !here || (!tgt && st.go && view() !== st.go) ? '<button class="btn sm" data-gd="go">Take me there</button>' : '';
      body = (s.path === 'real' ? '<ol class="gd-list">' + list.map(function (x, k) { return '<li class="' + (done[k] ? 'done' : k === i ? 'now' : '') + '"><span>' + (done[k] ? '✓' : k + 1) + '</span>' + esc(x.title) + '</li>'; }).join('') + '</ol>' : '') +
        '<h3 aria-live="polite">' + esc(st.title) + '</h3><p>' + esc(st.text) + '</p>' + (st.why ? '<p class="gd-why"><b>Why:</b> ' + esc(st.why) + '</p>' : '') +
        '<div class="gd-acts">' + goBtn + (st.ack ? '<button class="btn sm primary" data-gd="ack">Got it</button>' : '') +
        (i > 0 && s.path === 'sample' ? '<button class="btn sm ghost" data-gd="restart">Start over</button>' : '') + '<button class="btn sm ghost" data-gd="close">End the guide</button></div>';
      if (tgt && here) {
        tgt.classList.add('g-target');
        if (lastShown !== i) { var r = tgt.getBoundingClientRect(); if (r.top < 70 || r.bottom > innerHeight - panel.offsetHeight) tgt.scrollIntoView({ block: 'center', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); }
      }
    }
    panel.dataset.step = i;
    panel.innerHTML = head + bar + '<div class="gd-b">' + body + '</div>';
    if (lastShown !== i && lastShown !== -1) { var h = panel.querySelector('h3'); if (h) { h.setAttribute('tabindex', '-1'); } }
    lastShown = i;
  }

  function onPanelClick(e) {
    var b = e.target.closest('[data-gd]'); if (!b) return;
    var s = S() || {}, a = b.dataset.gd, list = steps(s);
    if (a === 'min') { s.min = true; save(s); return evaluate(); }
    if (a === 'open') { s.min = false; save(s); return evaluate(); }
    if (a === 'close') { store('cs_guide', null); hidePanel(); return A.toast('Guide closed. Reopen it from “Guide” in the band at the top.'); }
    if (a === 'again') { store('cs_guide', null); hidePanel(); return; }
    if (a === 'real') return start('real');
    if (a === 'restart') return start('sample', s.role);
    // The step on screen is the first not done: find it again rather than trusting a stale index.
    var n = +panel.dataset.step, st = list[n];
    if (!st) return;
    if (a === 'ack') { s.acked = s.acked || {}; s.acked[n] = true; save(s); return evaluate(); }
    if (a === 'go') {
      if (st.open) return changeBy(st.open).then(function (c) { if (c) { store('cs_change', c.id); A.go('change'); } });
      if (st.openFn) return st.openFn().then(function (c) { if (c) { store('cs_change', c.id); A.go('change'); } else A.go('home'); });
      if (st.go) return A.go(st.go);
    }
  }

  function start(path, role) {
    store('cs_seen_start', 1);
    if (path === 'sample') { save({ path: 'sample', role: role, acked: {} }); return P.enterSample('home'); }
    save({ path: 'real' });
    // Leave the sample if it's loaded: the page reloads into the live project database.
    store('cs_mode', 'live'); location.href = location.pathname + '#home'; location.reload();
  }
  app.addEventListener('click', function (e) {
    var b = e.target.closest('[data-gspath],[data-gsrole]'); if (!b) return;
    if (b.dataset.gspath === 'sample') return A.go('start?pick=role');
    if (b.dataset.gspath === 'real') return start('real');
    if (b.dataset.gsrole) return start('sample', b.dataset.gsrole);
  });
  // "Guide" in the band reopens the guide, or offers to start one.
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-guideopen]'); if (!b) return;
    var s = S(); if (s) { s.min = false; save(s); return evaluate(); }
    A.go(P.isSample() ? 'start?pick=role' : 'start');
  });

  // Re-check after every screen change. Screens redraw #app, so watching it catches every step.
  var t = null;
  function soon() { clearTimeout(t); t = setTimeout(evaluate, 250); }
  new MutationObserver(soon).observe(app, { childList: true });
  window.addEventListener('hashchange', soon);
  P.guideRefresh = soon;
})();
