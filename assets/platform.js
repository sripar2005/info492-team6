/* The platform's data layer: connecting (the in-browser sample or the live database), the current project and who you're
   viewing as, what each party may see (assets/rules.js), and loading the synthetic sample.
   The screens are in assets/views-platform.js. */
(function () {
  'use strict';
  var A = window.CSApp, store = A.store, esc = A.esc, R = window.CSRules;
  var P = window.CSPlat = {};
  var sb = null, cfg = null, user = null, ready = null, ctx = null;
  var ROLE = { owner: 'Owner', architect: 'Architect', gc: 'GC/CM', sub: 'Sub' };
  var TYPE = { gccm: 'GC/CM', hard_bid: 'Hard bid (design-bid-build)', design_build: 'Design-build' };
  P.ROLE = ROLE; P.TYPE = TYPE;

  /* ---------- sample or live ---------- */
  function isSample() { return store('cs_mode') === 'sample'; }
  P.isSample = isSample;
  P.enterSample = function (view) { store('cs_mode', 'sample'); store('cs_viewas', null); location.href = location.pathname + '#' + (view || 'home'); location.reload(); };
  P.leaveSample = function () { store('cs_mode', null); store('cs_project_sample', null); store('cs_viewas', null); location.href = location.pathname + '#home'; location.reload(); };
  function q(p) { return p.then(function (r) { if (r.error) throw new Error(r.error.message || String(r.error)); return r.data; }); }
  P.q = q;
  P.sb = function () { return sb; };
  P.user = function () { return user; };
  P.cfg = function () { return cfg; };

  P.connect = function () {
    if (ready) return ready;
    if (isSample()) {
      sb = window.CSDemo.make(); user = window.CSDemo.user; cfg = { configured: true, sample: true };
      ready = seedSample(sb, function () {}).then(function (pid) { store('cs_project_sample', pid); return loadCtx(pid); }).then(function () { P.band(); return sb; });
      return ready;
    }
    ready = fetch('/api/config').then(function (r) { return r.ok ? r.json() : { configured: false }; }).catch(function () { return { configured: false }; })
      .then(function (c) {
        cfg = c; if (!c.configured || !window.supabase) return null;
        sb = window.supabase.createClient(c.url, c.anonKey, { auth: { persistSession: true, detectSessionInUrl: true, flowType: 'pkce' } });
        sb.auth.onAuthStateChange(function (ev, session) {
          var was = user && user.id; user = session ? session.user : null;
          if (user && user.id !== was) sb.rpc('claim_invites').then(function () { P.rerender(); });
          else if (!user && was) P.rerender();
        });
        return sb.auth.getSession().then(function (r) { user = r.data.session ? r.data.session.user : null; if (user) return sb.rpc('claim_invites'); });
      }).then(function () {
        if (/[?&]signin=1/.test(location.search)) history.replaceState(null, '', location.pathname + '#home');
        var pid = store('cs_project');
        return pid && user ? loadCtx(pid).catch(function () { store('cs_project', null); ctx = null; }) : null;
      }).then(function () { P.band(); return sb; });
    return ready;
  };
  P.rerender = function () { var v = location.hash.slice(1).split('?')[0] || 'home'; var V = window.CSViews || {}; if (V[v]) V[v](); };

  /* ---------- the current project and who you're viewing as ---------- */
  function loadCtx(pid) {
    return Promise.all([
      q(sb.from('projects').select('*').eq('id', pid).single()),
      q(sb.from('project_companies').select('*').eq('project_id', pid)),
      q(sb.from('contracts').select('*').eq('project_id', pid)),
      q(sb.from('contract_terms').select('*').eq('project_id', pid)),
      user ? q(sb.from('company_people').select('company_id,is_admin').eq('user_id', user.id)) : Promise.resolve([])
    ]).then(function (r) {
      var pcs = r[1], ids = pcs.map(function (x) { return x.company_id; });
      return q(sb.from('companies').select('*').in('id', ids)).then(function (cos) {
        var C = {}; cos.forEach(function (c) { C[c.id] = c; });
        var role = {}; pcs.forEach(function (x) { role[x.company_id] = x.role; if (C[x.company_id]) C[x.company_id].role = x.role; });
        var K = {}; r[2].forEach(function (k) { K[k.id] = k; k.terms = {}; });
        r[3].forEach(function (t) { if (K[t.contract_id]) K[t.contract_id].terms[t.key] = t; });
        var mine = r[4].map(function (x) { return x.company_id; }).filter(function (id) { return role[id]; });
        ctx = { project: r[0], companies: C, role: role, contracts: K, mine: mine, admin: pcs.some(function (x) { return x.is_admin && mine.indexOf(x.company_id) >= 0; }) || r[0].created_by === (user && user.id) };
        var va = store(isSample() ? 'cs_viewas' : 'cs_viewas_live');
        if (!va || mine.indexOf(va) < 0) va = mine.filter(function (id) { return role[id] === 'gc'; })[0] || mine[0];
        ctx.viewAs = va;
        return ctx;
      });
    });
  }
  P.loadCtx = loadCtx;
  P.ctx = function () { return ctx; };
  P.openProject = function (pid) { store(isSample() ? 'cs_project_sample' : 'cs_project', pid); return loadCtx(pid).then(function () { P.band(); }); };
  P.closeProject = function () { store('cs_project', null); ctx = null; P.band(); };
  P.viewAs = function () { return ctx && ctx.viewAs; };
  P.roleOf = function (co) { return ctx && ctx.role[co]; };
  P.myRole = function () { return ctx && ctx.role[ctx.viewAs]; };
  P.setViewAs = function (co) { if (!ctx || ctx.mine.indexOf(co) < 0) return; ctx.viewAs = co; store(isSample() ? 'cs_viewas' : 'cs_viewas_live', co); P.band(); P.rerender(); };
  P.company = function (id) { return ctx && ctx.companies[id]; };
  P.coName = function (id) { var c = P.company(id); return c ? c.name : '—'; };
  P.byRole = function (role) { return Object.keys(ctx.companies).filter(function (id) { return ctx.role[id] === role; }); };
  P.prime = function () { return Object.keys(ctx.contracts).map(function (k) { return ctx.contracts[k]; }).filter(function (k) { return k.kind === 'prime'; })[0] || null; };
  P.subcontractOf = function (co) { return Object.keys(ctx.contracts).map(function (k) { return ctx.contracts[k]; }).filter(function (k) { return k.kind === 'sub' && k.down_company === co; })[0] || null; };
  P.term = function (k, key) { var t = k && k.terms[key]; return t ? t.value : null; };

  // What the company you're viewing as may see. On a real project the database has already filtered by your companies;
  // this narrows it to the one you're viewing as. On the sample and synthetic projects it's the whole rule.
  P.sees = {
    change: function (c) { return R.seesChange(c, ctx.viewAs, P.myRole()); },
    doc: function (d) { return R.seesDoc(d, ctx.viewAs, ctx.contracts); },
    contract: function (k) { return R.seesContract(k, ctx.viewAs); },
    sov: function (l) { return R.seesSov(l, ctx.viewAs, ctx.contracts); },
    event: function (e, changesById) { return R.seesEvent(e, ctx.viewAs, P.myRole(), changesById); }
  };

  /* ---------- the band under the header: sample or live, and who you're viewing as ---------- */
  P.band = function () {
    var el = document.getElementById('modeband'); if (!el) return;
    var sample = isSample();
    document.body.classList.toggle('is-sample', sample);
    el.hidden = false; el.className = 'modeband ' + (sample ? 'sample' : 'live');
    var picker = '';
    if (ctx && ctx.mine.length > 1) {
      var groups = ['owner', 'architect', 'gc', 'sub'];
      picker = '<label class="mb-as"><span>Signed in as</span><select id="viewas">' + groups.map(function (g) {
        var ids = ctx.mine.filter(function (id) { return ctx.role[id] === g; }); if (!ids.length) return '';
        return '<optgroup label="' + ROLE[g] + (g === 'sub' ? 's' : '') + '">' + ids.map(function (id) { return '<option value="' + id + '"' + (id === ctx.viewAs ? ' selected' : '') + '>' + esc(ctx.companies[id].name) + '</option>'; }).join('') + '</optgroup>';
      }).join('') + '</select></label>';
    }
    el.innerHTML = sample
      ? '<span class="mb-k">Sample project</span><span class="mb-t">Synthetic data written for this research. Not a real project, and nothing you do here is saved.</span>' + picker + '<button class="mb-b" data-guideopen="1">Guide</button><button class="mb-b" data-leavesample="1">Leave the sample</button>'
      : '<span class="mb-k">' + (ctx ? (ctx.project.synthetic ? 'Live account, synthetic project' : 'Live project') : 'Live') + '</span><span class="mb-t">' + (ctx ? esc(ctx.project.name) + '. Saved, and each party sees only what its contracts allow.' : 'Sign in to open a real project, or try the sample.') + '</span>' + picker +
        '<button class="mb-b" data-guideopen="1">Guide</button>' + (ctx ? '' : '<button class="mb-b" data-entersample="1">Open the sample</button>');
    var s = document.getElementById('viewas'); if (s) s.onchange = function () { P.setViewAs(s.value); };
  };

  /* ---------- the synthetic sample ---------- */
  // Prime contract terms the clocks and checks use. Values and sentences are from contract A (demo1/data/synthetic_contract.md).
  var PRIME_EXTRA = {
    cp_days: { value: 21, section: '6.3', quote: 'After a notice under Section 6.2, CM shall submit a CP within 21 days.' },
    review_days: { value: 14, section: '6.4', quote: 'Owner, through Architect, shall respond to a complete CP within 14 days after receipt.' },
    rfi_days: { value: 10, section: '7.3', quote: 'Architect shall respond to each RFI within 10 days after receipt.' }
  };
  function getJSON(u) { return fetch(u).then(function (r) { if (!r.ok) throw new Error('Could not load ' + u); return r.json(); }); }
  function getText(u) { return fetch(u).then(function (r) { return r.ok ? r.text() : ''; }).catch(function () { return ''; }); }
  function chunk(a, n) { var o = []; for (var i = 0; i < a.length; i += n) o.push(a.slice(i, i + n)); return o; }
  function seq(list, fn) { return list.reduce(function (p, x) { return p.then(function () { return fn(x); }); }, Promise.resolve()); }
  P.splitPieces = null; // set by the views (shared splitter)

  function seedSample(sb, progress) {
    return Promise.all([getJSON('/record/bundle.json'), getJSON('/record/platform/platform.json').catch(function () { return null; }), getJSON('/demo4/data/contract_terms_key.json'),
      getJSON('/demo3/data/cases.json'), getJSON('/demo4/data/cases.json')]).then(function (r) {
      var B = r[0], PL = r[1] || { companies: [], contracts: [], sov: [], schedule_versions: [], sub_requests: [], field_samples: [] }, TK = r[2].contracts.A.terms;
      var cases = {}; r[3].cases.concat(r[4].cases).forEach(function (c) { cases[c.id] = c; });
      var co = {}, names = {}, pid;
      var gcInfo = PL.companies.filter(function (c) { return c.kind === 'gc'; })[0] || { key: 'gc', name: 'Sample GC/CM', kind: 'gc' };
      return q(sb.rpc('start_project', { p_name: B.project.name, p_type: (PL.project && PL.project.contract_type) || 'gccm', p_company: gcInfo.name, p_role: 'gc', p_synthetic: true }))
        .then(function (id) { pid = id; return q(sb.from('project_companies').select('company_id').eq('project_id', pid)); })
        .then(function (rows) {
          co[gcInfo.key] = rows[0].company_id; names[rows[0].company_id] = gcInfo.name;
          var others = PL.companies.filter(function (c) { return c.kind !== 'gc'; });
          if (!others.some(function (c) { return c.kind === 'owner'; })) others.unshift({ key: 'owner', name: B.project.owner_org || 'Owner', kind: 'owner' });
          return seq(others, function (c) { return q(sb.rpc('add_sample_company', { p: pid, p_name: c.name, p_kind: c.kind, p_trade: c.trade || null })).then(function (id) { co[c.key] = id; names[id] = c.name; }); });
        }).then(function () {
          progress('contracts');
          var Ks = PL.contracts.length ? PL.contracts : [{ key: 'prime', kind: 'prime', up: 'owner', down: gcInfo.key, title: 'Prime contract (GC/CM)' }];
          var kid = {};
          return seq(Ks.filter(function (k) { return co[k.up] && co[k.down]; }), function (k) {
            return q(sb.from('contracts').insert({ project_id: pid, kind: k.kind, up_company: co[k.up], down_company: co[k.down], parent_id: k.parent ? kid[k.parent] || null : null, title: k.title, meta: { key: k.key, file: k.file || null, document_key: k.document_key || null } }).select().single())
              .then(function (row) {
                kid[k.key] = row.id;
                var byKey = {};
                if (k.kind === 'prime') {
                  Object.keys(TK).forEach(function (key) { byKey[key] = { value: TK[key].value, clause: '§ ' + TK[key].section, sentence: TK[key].quote }; });
                  Object.keys(PRIME_EXTRA).forEach(function (key) { byKey[key] = { value: PRIME_EXTRA[key].value, clause: '§ ' + PRIME_EXTRA[key].section, sentence: PRIME_EXTRA[key].quote }; });
                }
                (k.terms || []).forEach(function (t) { if (!byKey[t.key]) byKey[t.key] = { value: t.value, clause: t.clause, sentence: t.sentence }; });
                var terms = Object.keys(byKey).map(function (key) { var t = byKey[key]; return { project_id: pid, contract_id: row.id, key: key, value: t.value, clause: t.clause, sentence: t.sentence }; });
                return terms.length ? q(sb.from('contract_terms').insert(terms)) : null;
              });
          }).then(function () { return kid; });
        }).then(function (kid) {
          progress('record');
          // Documents: the bundle's record (everyone on the project), plus each subcontract and the design summary (their parties only).
          var docs = B.documents.map(function (d) {
            var isPrime = d.kind === 'contract';
            return { key: d.key, row: { project_id: pid, kind: d.kind, number: d.number, title: d.title, issued_on: d.issued_on || null, author_company: co[d.author_party === 'gc' ? gcInfo.key : d.author_party] || null, visibility: 'project', source: 'synthetic', external_id: d.external_id, meta: Object.assign({}, d.meta || {}, { key: d.key, file: d.file || null, prime: isPrime }) }, pieces: d.pieces || [] };
          });
          var extra = PL.contracts.filter(function (k) { return k.file && kid[k.key]; });
          return Promise.all(extra.map(function (k) { return getText('/' + k.file); })).then(function (texts) {
            extra.forEach(function (k, i) {
              if (!texts[i]) return;
              docs.push({ key: 'k:' + k.key, row: { project_id: pid, kind: 'contract', number: null, title: k.title, issued_on: null, author_company: co[k.up] || null, visibility: 'contract', contract_id: kid[k.key], source: 'synthetic', external_id: 'syn:' + k.key, meta: { key: 'k:' + k.key, file: k.file } },
                pieces: P.splitPieces ? P.splitPieces('contract', texts[i], null, null) : [{ ordinal: 1, section: null, body: texts[i] }] });
            });
            var keyToDoc = {}, pieceIds = {};
            return seq(chunk(docs, 100), function (c) {
              return q(sb.from('documents').insert(c.map(function (d) { return d.row; })).select('id,meta')).then(function (out) { out.forEach(function (o) { keyToDoc[o.meta.key] = o.id; }); });
            }).then(function () {
              var all = []; docs.forEach(function (d) { d.pieces.forEach(function (pc) { all.push({ project_id: pid, document_id: keyToDoc[d.key], ordinal: pc.ordinal, section: pc.section || null, body: pc.body, piece_date: pc.piece_date || null, company_id: co[pc.party === 'gc' ? gcInfo.key : pc.party] || null, meta: { key: d.key } }); }); });
              return seq(chunk(all, 300), function (c) { return q(sb.from('pieces').insert(c).select('id,section,meta')).then(function (out) { out.forEach(function (o) { pieceIds[o.meta.key + '|' + o.section] = o.id; }); }); });
            }).then(function () {
              var ls = (B.links || []).filter(function (l) { return keyToDoc[l.from] && keyToDoc[l.to]; }).map(function (l) {
                return { project_id: pid, from_doc: keyToDoc[l.from], to_doc: keyToDoc[l.to], relation: l.relation, from_piece: l.from_section ? pieceIds[l.from + '|' + l.from_section] || null : null, to_piece: l.to_section ? pieceIds[l.to + '|' + l.to_section] || null : null };
              });
              return seq(chunk(ls, 300), function (c) { return q(sb.from('links').insert(c)); });
            }).then(function () {
              // Point each contract at its document.
              var primeDoc = B.documents.filter(function (d) { return d.kind === 'contract'; })[0];
              return seq(Object.keys(kid), function (k) {
                var d = k === 'prime' && primeDoc ? keyToDoc[primeDoc.key] : keyToDoc['k:' + k];
                return d ? q(sb.from('contracts').update({ document_id: d }).eq('id', kid[k])) : null;
              });
            }).then(function () { return { kid: kid, keyToDoc: keyToDoc }; });
          });
        }).then(function (m) {
          progress('money and schedule');
          var sov = (PL.sov || []).filter(function (l) { return m.kid[l.contract]; }).map(function (l) { return { project_id: pid, contract_id: m.kid[l.contract], code: l.code || null, description: l.description, amount: l.amount, general_conditions: !!l.general_conditions, basis: l.basis || null }; });
          var sv = PL.schedule_versions && PL.schedule_versions.length ? PL.schedule_versions : [{ key: 'u1', label: 'Update 1', data_date: '2020-06-01', file: 'demo4/data/schedule.json', caused_by: null }];
          return (sov.length ? q(sb.from('sov_lines').insert(sov)) : Promise.resolve()).then(function () {
            return seq(sv, function (v) {
              return getJSON('/' + v.file).then(function (data) {
                return q(sb.from('schedule_versions').insert({ project_id: pid, label: v.label, data_date: v.data_date || data.data_date || null, data: data, caused_by: v.caused_by || [], is_baseline: v.key === 'baseline' || /baseline/i.test(v.label) }));
              }).catch(function () { return null; });
            });
          }).then(function () { return m; });
        }).then(function (m) {
          progress('changes');
          // The sample's state: most changes are history (approved, imported from the record); a few are open so each party
          // has something to do. Open ones that are already with the architect or owner went through the real steps:
          // numbers confirmed, the checks computed by code, then sent.
          var OPEN = { 'CP-0212': 'draft', 'CP-0401': 'draft', 'CP-0403': 'draft', 'CP-0406': 'draft', 'CP-0225': 'returned', 'CP-0220': 'with_architect', 'CP-0230': 'with_owner' };
          var cos = B.documents.filter(function (d) { return d.kind === 'change_order'; });
          var owner = co.owner, gc = co[gcInfo.key], arch = co.architect || null;
          var ago = function (n) { return new Date(Date.now() - n * 864e5).toISOString(); };
          var rows = cos.map(function (d) {
            var c = cases[d.number] || {}, meta = d.meta || {}, open = OPEN[d.number];
            return { project_id: pid, number: d.number, title: String(d.title).replace(new RegExp('^' + d.number + '[\\s:–-]*'), ''), tier: 'proposal', contract_id: m.kid.prime || null, from_company: gc, to_company: owner,
              status: open ? 'draft' : 'approved', holder: open ? gc : null,
              amount: meta.total_requested != null ? meta.total_requested : (c.cover_sheet || {}).total_requested || null, days: c.time_impact_days || 0,
              cause: meta.cause || c.cause || {}, document_id: m.keyToDoc[d.key] || null, meta: { notice_date: meta.notice_date || c.notice_date || null, cp_submitted: meta.cp_submitted || c.cp_submitted || null, case_id: c.id || null, history: !open } };
          });
          return seq(chunk(rows, 100), function (c) { return q(sb.from('changes').insert(c)); }).then(function () { return q(sb.from('changes').select('id,number,status').eq('project_id', pid)); })
            .then(function (props) {
              var byNum = {}; props.forEach(function (p) { byNum[p.number] = p.id; });
              var reqs = (PL.sub_requests || []).filter(function (s) { return co[s.from] && byNum[s.change]; }).map(function (s) {
                var sub = PL.contracts.filter(function (k) { return k.kind === 'sub' && k.down === s.from; })[0], open = OPEN[s.change], waiting = open === 'draft';
                return { project_id: pid, number: s.key, title: s.title || (s.narrative || '').split(/[.\n]/)[0].slice(0, 80) || ('Change request for ' + s.change), tier: 'sub_request', contract_id: sub ? m.kid[sub.key] || null : null,
                  from_company: co[s.from], to_company: co[s.to] || gc, amount: s.amount, days: s.days || 0,
                  status: waiting ? 'draft' : open ? 'bundled' : 'approved', holder: waiting ? co[s.from] : open ? gc : null, parent_id: waiting ? null : byNum[s.change],
                  meta: { for_change: s.change, sub_number: s.number || null, submitted: s.submitted || null, lines: s.lines || [], lower_tier: s.lower_tier || [], narrative: s.narrative || '', history: !open } };
              });
              return (reqs.length ? q(sb.from('changes').insert(reqs).select('id,from_company,status,meta')) : Promise.resolve([])).then(function (out) {
                var evs = [], reqSummary = {};
                out.forEach(function (x) {
                  if (x.meta.narrative) evs.push({ project_id: pid, change_id: x.id, company_id: x.from_company, kind: 'note', body: x.meta.narrative, created_at: x.meta.submitted ? x.meta.submitted + 'T15:00:00Z' : undefined });
                  if (x.status === 'draft') evs.push({ project_id: pid, change_id: x.id, company_id: x.from_company, kind: 'submit', body: 'Sent to the GC/CM.' });
                  else (reqSummary[x.meta.for_change] = reqSummary[x.meta.for_change] || []).push(x);
                });
                cos.forEach(function (d) {
                  var cause = (d.meta || {}).cause, when = (d.meta || {}).notice_date;
                  evs.push({ project_id: pid, change_id: byNum[d.number], company_id: gc, kind: 'note', body: (cause ? 'Raised from ' + (cause.reference || cause.type) + (cause.event_date ? ' (' + cause.event_date + ')' : '') + '.' : 'Raised.') + (OPEN[d.number] ? '' : ' History imported from the record: approved.'), created_at: when ? when + 'T15:00:00Z' : undefined });
                });
                evs.forEach(function (e) { if (e.created_at === undefined) delete e.created_at; });
                return seq(chunk(evs, 200), function (c) { return q(sb.from('events').insert(c)); }).then(function () {
                  // Proposals list the sub requests in them (number, company, amount) for the owner and architect.
                  return seq(Object.keys(reqSummary), function (num) {
                    return q(sb.from('changes').select('meta').eq('id', byNum[num]).single()).then(function (row) {
                      var rq = reqSummary[num].map(function (x) { var src = reqs.filter(function (y) { return y.meta.sub_number === x.meta.sub_number && y.meta.for_change === num && y.from_company === x.from_company; })[0] || {}; return { number: src.number, company: names[x.from_company] || '', amount: +src.amount || 0 }; });
                      return q(sb.from('changes').update({ meta: Object.assign({}, row.meta, { requests: rq }) }).eq('id', byNum[num]));
                    });
                  });
                }).then(function () {
                  // The open proposals already past the GC/CM: confirm, checks (computed now), explanation if needed, send, and onward.
                  var K = window.ClauseChecks, C = A.C();
                  return seq(Object.keys(OPEN).filter(function (n) { return OPEN[n] !== 'draft' && byNum[n]; }), function (num) {
                    var cid = byNum[num], cs = cases[num], st = OPEN[num], start = st === 'with_owner' ? 24 : st === 'returned' ? 12 : 19;
                    var sheet = cs && K ? K.checksheet(cs, C) : null, n = sheet ? sheet.counts : { fail: 0, pass: 0, person: 0 };
                    var steps = [{ kind: 'confirm', body: 'Total ' + A.M((cs && cs.cover_sheet || {}).total_requested || 0) + ' confirmed.', payload: { total: (cs && cs.cover_sheet || {}).total_requested || null }, created_at: ago(start + 1) },
                      { kind: 'check', body: n.pass + ' checks passed, ' + n.fail + ' to fix, ' + n.person + ' for a person. Checked by code against ' + C.name + '.', payload: { findings: n.fail, counts: n }, created_at: ago(start + 1) }];
                    if (n.fail) steps.push({ kind: 'explain', body: 'Explained in the cover letter; left as priced for the architect to review.', created_at: ago(start + 1) });
                    steps.push({ kind: 'submit', body: 'Sent with the evidence trail.', created_at: ago(start) });
                    if (st === 'with_owner') steps.push({ kind: 'forward', company: arch, body: 'Scope matches the documents. Recommend approval.', created_at: ago(start - 6) });
                    if (st === 'returned') steps.push({ kind: 'return', company: arch, reason: 'markup_over_limit', body: 'Sub markup on own work is over the contract limit. Revise and resubmit.', created_at: ago(start - 9) });
                    return seq(steps, function (e) {
                      if ((e.kind === 'forward' || e.kind === 'return') && !arch) return null;
                      return q(sb.from('events').insert({ project_id: pid, change_id: cid, company_id: e.company || gc, kind: e.kind, body: e.body, reason: e.reason || null, payload: e.payload || {}, created_at: e.created_at }));
                    });
                  });
                });
              });
            }).then(function () { return m; });
        }).then(function () {
          progress('field links');
          var subs = PL.companies.filter(function (c) { return c.kind === 'sub' && (c.tier || 1) === 1 && co[c.key]; });
          return seq(subs, function (c) { return q(sb.from('field_links').insert({ project_id: pid, company_id: co[c.key] }).select().single()).then(function (l) { c._token = l.token; }); })
            .then(function () {
              return seq(PL.field_samples || [], function (f) {
                var c = subs.filter(function (x) { return x.key === f.from; })[0]; if (!c) return null;
                return q(sb.rpc('submit_field', { p_token: c._token, p_body: f.text, p_name: f.name || '' }));
              });
            });
        }).then(function () { return pid; });
    });
  }
  P.seedSample = seedSample;
})();
