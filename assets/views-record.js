/* The shared project record: sign-in, projects, members, and one thread per change that every party works in.
   Data lives in Supabase (supabase/migrations). Access is decided there by row-level security, not here. */
(function () {
  'use strict';
  var A = window.CSApp, esc = A.esc, store = A.store, app = A.app;
  var V = window.CSViews = window.CSViews || {};
  var sb = null, cfg = null, user = null, ready = null, people = {};
  var PARTY = { sub: 'Sub', gc: 'GC/CM', architect: 'Architect', owner: 'Owner’s rep' };
  var NEXT = { sub: 'gc', gc: 'architect', architect: 'owner' }, PREV = { owner: 'architect', architect: 'gc', gc: 'sub' };
  var STATUS = { draft: 'Draft', with_gc: 'With GC/CM', with_architect: 'With architect', with_owner: 'With owner’s rep', returned: 'Returned', approved: 'Approved', rejected: 'Rejected', withdrawn: 'Withdrawn' };
  var REASONS = [['missing_backup', 'Backup missing or unclear'], ['markup_over_limit', 'Markup over the contract limit'], ['fee_on_excluded', 'Fee on excluded items'],
    ['late_notice', 'Notice given late'], ['quantities_unclear', 'Quantities or rates unclear'], ['not_a_change', 'Work is already in the contract'],
    ['needs_time_analysis', 'Time claim needs schedule analysis'], ['wrong_party', 'Wrong party is paying'], ['other', 'Other']];
  var KIND = { note: 'Note', draft: 'Draft', check: 'Check', submit: 'Sent up', return: 'Returned', approve: 'Approved', reject: 'Rejected', comment: 'Comment', link: 'Linked', attach: 'Attached', evidence: 'Evidence' };

  /* ---------- connection ---------- */
  function connect() {
    if (ready) return ready;
    ready = fetch('/api/config').then(function (r) { return r.ok ? r.json() : { configured: false }; }).catch(function () { return { configured: false }; })
      .then(function (c) {
        cfg = c; if (!c.configured || !window.supabase) return null;
        sb = window.supabase.createClient(c.url, c.anonKey, { auth: { persistSession: true, detectSessionInUrl: true, flowType: 'pkce' } });
        sb.auth.onAuthStateChange(function (ev, session) {
          var was = user && user.id; user = session ? session.user : null;
          if (user && user.id !== was) sb.rpc('claim_invites').then(function () { rerender(); });
          else if (!user && was) rerender();
        });
        return sb.auth.getSession().then(function (r) { user = r.data.session ? r.data.session.user : null; if (user) return sb.rpc('claim_invites'); });
      }).then(function () {
        if (/[?&]signin=1/.test(location.search)) { history.replaceState(null, '', location.pathname + '#project'); A.go('project'); }
        return sb;
      });
    return ready;
  }
  function rerender() { var v = location.hash.slice(1).split('?')[0]; if (V[v] && /^(project|changes|change|record|doc)$/.test(v)) V[v](); }
  function sheet(title, eyebrow, body) { return '<div class="wrap"><div class="ph1"><div><span class="eyebrow">' + esc(eyebrow) + '</span><h1 style="margin-top:8px">' + esc(title) + '</h1></div></div>' + body + '</div>'; }
  function fail(e) { A.toast((e && e.message) || String(e)); }
  function q(p) { return p.then(function (r) { if (r.error) throw r.error; return r.data; }); }
  function proj() { return store('cs_project'); }
  function setProj(p) { store('cs_project', p ? { id: p.id, name: p.name, synthetic: p.synthetic, party: p.party, is_admin: p.is_admin } : null); }
  function when(d) { var t = new Date(d); return t.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ', ' + t.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }); }

  function gate(render) {
    app.innerHTML = '<div class="wrap"><div class="reading"><div class="spinner"></div><h2>Opening the project record…</h2></div></div>';
    connect().then(function () {
      if (!cfg || !cfg.configured) return app.innerHTML = sheet('Project record', 'A-001', '<div class="banner warn"><span>The shared record runs on the live site (it needs the project database). Open <a class="link" href="https://info492-team6.vercel.app/check/#project">info492-team6.vercel.app</a>.</span></div>');
      if (!user) return signIn();
      render();
    }).catch(fail);
  }
  function signIn(sent) {
    app.innerHTML = sheet('Sign in to the project record', 'A-001 · Project', '<div class="card sec" style="max-width:520px">' +
      (sent ? '<p style="margin:0 0 6px"><b>Check your email.</b> We sent a sign-in link to ' + esc(sent) + '. Open it in this browser.</p><p class="fine" style="margin:0">No password. The link works once and expires after an hour.</p>'
        : '<p style="margin:0 0 14px;color:var(--muted)">Everyone on a project (sub, GC/CM, architect, owner’s rep) works from the same record. Sign in with your email; we send a one-time link.</p>' +
          '<form id="signin" class="grid" style="grid-template-columns:minmax(0,1fr) auto;gap:10px"><div class="inp"><input type="email" id="email" required placeholder="you@company.com" autocomplete="email"></div><button class="btn primary" type="submit">Email me a link</button></form>') + '</div>');
    var f = document.getElementById('signin');
    if (f) f.addEventListener('submit', function (e) {
      e.preventDefault(); var email = document.getElementById('email').value.trim();
      q(sb.auth.signInWithOtp({ email: email, options: { emailRedirectTo: location.origin + '/check/?signin=1' } })).then(function () { signIn(email); }).catch(fail);
    });
  }

  /* ---------- A-001 Project: my projects, members, invites ---------- */
  V.project = function () {
    gate(function () {
      Promise.all([q(sb.from('projects').select('id,name,synthetic,created_at').order('created_at', { ascending: false })), q(sb.from('members').select('project_id,party,is_admin').eq('user_id', user.id))])
        .then(function (r) {
          var mine = {}; r[1].forEach(function (m) { mine[m.project_id] = m; });
          var list = r[0].map(function (p) { return Object.assign({}, p, mine[p.id] || {}); }), cur = proj();
          if (cur && !list.some(function (p) { return p.id === cur.id; })) { setProj(null); cur = null; }
          var rows = list.map(function (p) {
            return '<tr><td><span class="t">' + esc(p.name) + '</span><span class="id">' + (p.synthetic ? 'Synthetic sample' : 'Project') + '</span></td><td>' + esc(PARTY[p.party] || '—') + (p.is_admin ? ' · admin' : '') + '</td><td>' +
              (cur && cur.id === p.id ? '<b>Open</b>' : '<button class="btn sm" data-popen="' + p.id + '">Open</button>') + '</td></tr>';
          }).join('');
          var body = '<p style="margin:-6px 0 18px;color:var(--muted)">Signed in as <b>' + esc(user.email) + '</b>. <button class="link" data-signout="1">Sign out</button></p>' +
            '<div class="cols" style="grid-template-columns:minmax(0,1.3fr) minmax(0,1fr)"><div>' +
            (list.length ? '<div class="card tbl-wrap"><table class="tbl"><thead><tr><th>Project</th><th>You are</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>'
              : '<div class="card sec"><p style="margin:0">No projects yet. Create one, or load the synthetic sample project to try the full flow. You may also have been invited: invites appear here after you sign in with the invited email.</p></div>') +
            '<div class="card sec" style="margin-top:16px"><div class="sec-h"><h3>New project</h3></div><form id="newp" class="grid"><div class="fd"><label><span>Name</span></label><div class="inp"><input id="pname" required placeholder="e.g. Juanita HS modernization"></div></div>' +
            '<div class="fd"><label><span>You are the</span></label><div class="inp sel"><select id="pparty">' + Object.keys(PARTY).map(function (k) { return '<option value="' + k + '"' + (k === 'gc' ? ' selected' : '') + '>' + PARTY[k] + '</option>'; }).join('') + '</select></div></div>' +
            '<div class="fd full"><button class="btn primary" type="submit">Create project</button> <button class="btn" type="button" data-loadsample="1">Load the synthetic sample project</button></div></form></div></div>' +
            '<div id="pdetail">' + (cur ? '<div class="card sec"><p class="fine" style="margin:0">Loading members…</p></div>' : '<div class="card sec"><p style="margin:0;color:var(--muted)">Open a project to see who is on it and to invite the other parties.</p></div>') + '</div></div>';
          app.innerHTML = sheet('Projects', 'A-001 · Project', body);
          if (cur) detail(cur);
        }).catch(fail);
    });
  };
  function detail(cur) {
    Promise.all([q(sb.rpc('project_people', { p: cur.id })), q(sb.from('invites').select('email,party').eq('project_id', cur.id)), q(sb.from('documents').select('kind', { count: 'exact', head: false }).eq('project_id', cur.id))])
      .then(function (r) {
        people = {}; r[0].forEach(function (m) { people[m.user_id] = m; });
        var counts = {}; r[2].forEach(function (d) { counts[d.kind] = (counts[d.kind] || 0) + 1; });
        var el = document.getElementById('pdetail'); if (!el) return;
        el.innerHTML = '<div class="card sec"><div class="sec-h"><h3>' + esc(cur.name) + '</h3>' + (cur.synthetic ? '<span class="tagr none">synthetic</span>' : '') + '</div>' +
          '<ul class="qual">' + r[0].map(function (m) { return '<li class="info"><span class="qd"></span><div><b>' + esc(PARTY[m.party]) + '</b> ' + esc(m.email || '') + (m.is_admin ? ' · admin' : '') + '</div></li>'; }).join('') +
          r[1].map(function (i) { return '<li class="info"><span class="qd"></span><div><b>' + esc(PARTY[i.party]) + '</b> ' + esc(i.email) + ' <span class="fine">· invited</span></div></li>'; }).join('') + '</ul>' +
          (cur.is_admin ? '<form id="inv" class="grid" style="margin-top:14px"><div class="fd"><label><span>Invite by email</span></label><div class="inp"><input id="iemail" type="email" required placeholder="architect@firm.com"></div></div><div class="fd"><label><span>As the</span></label><div class="inp sel"><select id="iparty">' +
            Object.keys(PARTY).map(function (k) { return '<option value="' + k + '">' + PARTY[k] + '</option>'; }).join('') + '</select></div></div><div class="fd full"><button class="btn sm" type="submit">Invite</button><span class="fine" style="margin-left:10px">They join when they sign in with that email.</span></div></form>' : '') +
          '<div class="sec-h" style="margin-top:18px"><h3>Record</h3><a class="link" href="#record">Open</a></div><p class="fine" style="margin:0">' + (Object.keys(counts).length ? Object.keys(counts).map(function (k) { return counts[k] + ' ' + k.replace('_', ' '); }).join(', ') : 'No documents yet.') + '</p>' +
          '<div class="acts" style="margin-top:16px"><a class="btn primary" href="#changes">Open changes</a></div></div>';
        var f = document.getElementById('inv');
        if (f) f.addEventListener('submit', function (e) { e.preventDefault(); q(sb.from('invites').insert({ project_id: cur.id, email: document.getElementById('iemail').value.trim().toLowerCase(), party: document.getElementById('iparty').value })).then(function () { A.toast('Invited.'); detail(cur); }).catch(fail); });
      }).catch(fail);
  }
  function createProject(name, party, synthetic) {
    return q(sb.from('projects').insert({ name: name, synthetic: !!synthetic }).select().single()).then(function (p) {
      return (party && party !== 'gc' ? q(sb.from('members').update({ party: party }).eq('project_id', p.id).eq('user_id', user.id)) : Promise.resolve()).then(function () { setProj(Object.assign(p, { party: party || 'gc', is_admin: true })); return p; });
    });
  }

  /* ---------- import a record bundle (the synthetic set now; real documents and Procore later use the same path) ---------- */
  function importBundle(projectId, bundle, progress) {
    var keyToDoc = {}, docs = bundle.documents;
    function chunk(a, n) { var o = []; for (var i = 0; i < a.length; i += n) o.push(a.slice(i, i + n)); return o; }
    var rows = docs.map(function (d) { return { project_id: projectId, kind: d.kind, number: d.number, title: d.title, issued_on: d.issued_on || null, author_party: d.author_party || null, source: d.source || 'upload', external_id: d.external_id || null, meta: Object.assign({}, d.meta || {}, { key: d.key, file: d.file || null }) }; });
    var p = Promise.resolve();
    chunk(rows, 100).forEach(function (c) { p = p.then(function () { return q(sb.from('documents').insert(c).select('id,number,meta')).then(function (out) { out.forEach(function (o) { keyToDoc[o.meta.key || o.number] = o.id; }); progress('documents', Object.keys(keyToDoc).length, docs.length); }); }); });
    var pieceIds = {};
    p = p.then(function () {
      var all = []; docs.forEach(function (d) { (d.pieces || []).forEach(function (pc) { all.push({ project_id: projectId, document_id: keyToDoc[d.key], ordinal: pc.ordinal, section: pc.section || null, body: pc.body, piece_date: pc.piece_date || null, party: pc.party || null, meta: { key: d.key } }); }); });
      var done = 0, pp = Promise.resolve();
      chunk(all, 250).forEach(function (c) { pp = pp.then(function () { return q(sb.from('pieces').insert(c).select('id,section,meta')).then(function (out) { out.forEach(function (o) { pieceIds[o.meta.key + '|' + o.section] = o.id; }); done += c.length; progress('pieces', done, all.length); }); }); });
      return pp;
    });
    return p.then(function () {
      var ls = (bundle.links || []).filter(function (l) { return keyToDoc[l.from] && keyToDoc[l.to]; }).map(function (l) {
        return { project_id: projectId, from_doc: keyToDoc[l.from], to_doc: keyToDoc[l.to], relation: l.relation, from_piece: l.from_section ? pieceIds[l.from + '|' + l.from_section] || null : null, to_piece: l.to_section ? pieceIds[l.to + '|' + l.to_section] || null : null };
      });
      var pl = Promise.resolve(); chunk(ls, 250).forEach(function (c) { pl = pl.then(function () { return q(sb.from('links').insert(c)); }); });
      return pl.then(function () { progress('links', ls.length, ls.length); return { documents: docs.length, links: ls.length }; });
    });
  }
  function loadSample() {
    app.innerHTML = '<div class="wrap"><div class="reading"><div class="spinner"></div><h2>Loading the synthetic sample project</h2><p class="fine" id="prog">Reading the record…</p></div></div>';
    fetch('/record/bundle.json').then(function (r) { if (!r.ok) throw new Error('The sample record is not published yet.'); return r.json(); }).then(function (b) {
      return createProject(b.project.name, 'gc', true).then(function (p) {
        return importBundle(p.id, b, function (what, n, of) { var el = document.getElementById('prog'); if (el) el.textContent = 'Saving ' + what + ': ' + n + ' of ' + of; }).then(function (res) {
          return seedThreads(p.id, b).then(function (nt) { A.toast('Loaded ' + res.documents + ' documents, ' + res.links + ' links, ' + nt + ' changes.'); A.go('changes'); });
        });
      });
    }).catch(function (e) { fail(e); V.project(); });
  }
  // One thread per change order in the record, opened by the sub with the plain-language note.
  function seedThreads(projectId, b) {
    var cos = b.documents.filter(function (d) { return d.kind === 'change_order'; });
    if (!cos.length) return Promise.resolve(0);
    return q(sb.from('documents').select('id,number').eq('project_id', projectId).eq('kind', 'change_order')).then(function (docs) {
      var byNum = {}; docs.forEach(function (d) { byNum[d.number] = d.id; });
      var rows = cos.map(function (d) { return { project_id: projectId, number: d.number, title: String(d.title).replace(new RegExp('^' + d.number + '[\\s:–-]*'), ''), holder: 'sub', status: 'draft', document_id: byNum[d.number] || null }; });
      return q(sb.from('threads').insert(rows).select('id,number')).then(function (ts) {
        var ev = ts.map(function (t) { var d = cos.filter(function (c) { return c.number === t.number; })[0]; var note = (d.meta && d.meta.plain_note) || ((d.pieces || [])[0] || {}).body || d.title; return { thread_id: t.id, project_id: projectId, party: 'sub', kind: 'note', body: note, actor: user.id }; });
        return q(sb.from('events').insert(ev)).then(function () { return ts.length; });
      });
    });
  }

  /* ---------- T-201 Changes: every change on the project, who holds it ---------- */
  V.changes = function () {
    gate(function () {
      var cur = proj(); if (!cur) return A.go('project');
      q(sb.from('threads').select('id,number,title,status,holder,updated_at').eq('project_id', cur.id).order('number')).then(function (ts) {
        var me = actingParty(cur), mine = ts.filter(function (t) { return t.holder === me && !/approved|rejected|withdrawn/.test(t.status); }).length;
        var rows = ts.map(function (t) {
          return '<tr data-topen="' + t.id + '"><td><span class="t">' + esc(t.title) + '</span><span class="id">' + esc(t.number) + '</span></td><td><span class="badge' + (t.status === 'approved' ? ' ok' : t.status === 'returned' ? ' fail' : '') + '">' + esc(STATUS[t.status]) + '</span></td><td>' + (/approved|rejected|withdrawn/.test(t.status) ? '—' : esc(PARTY[t.holder])) + '</td><td class="fine" style="white-space:nowrap">' + when(t.updated_at) + '</td></tr>';
        }).join('');
        app.innerHTML = sheet('Changes', 'T-201 · ' + cur.name, '<p style="margin:-6px 0 16px;color:var(--muted)">' + ts.length + ' changes. ' + mine + ' waiting on you (' + esc(PARTY[me]) + '). <a class="link" href="#project">Switch project</a></p>' +
          '<div class="cols" style="grid-template-columns:minmax(0,1.5fr) minmax(0,1fr)"><div class="card tbl-wrap">' + (ts.length ? '<table class="tbl"><thead><tr><th>Change</th><th>Status</th><th>With</th><th>Updated</th></tr></thead><tbody>' + rows + '</tbody></table>' : '<p style="padding:18px;margin:0">No changes yet.</p>') + '</div>' +
          '<div class="card sec"><div class="sec-h"><h3>Raise a change</h3></div><p class="fine" style="margin:0 0 10px">Write it the way you’d say it on site. The formal proposal is drafted from the record next.</p><form id="newt"><div class="fd"><label><span>Short title</span></label><div class="inp"><input id="ttitle" required placeholder="e.g. Extra drains at gym roof"></div></div>' +
          '<div class="fd" style="margin-top:10px"><label><span>What happened</span></label><div class="inp" style="height:auto"><textarea id="tnote" rows="5" required placeholder="e.g. RFI-112 answer adds two roof drains at the gym. We need to tie into the existing leader and cut the deck. About 3 days for our crew."></textarea></div></div>' +
          '<button class="btn primary" type="submit" style="margin-top:12px">Raise it</button></form></div></div>');
        document.getElementById('newt').addEventListener('submit', function (e) {
          e.preventDefault();
          var n = ts.reduce(function (m, t) { var k = parseInt(String(t.number).replace(/\D/g, ''), 10); return isFinite(k) && k > m ? k : m; }, 600) + 1;
          var party = actingParty(cur);
          q(sb.from('threads').insert({ project_id: cur.id, number: 'CP-' + ('000' + n).slice(-4), title: document.getElementById('ttitle').value.trim(), holder: party }).select().single()).then(function (t) {
            return q(sb.from('events').insert({ thread_id: t.id, project_id: cur.id, party: party, kind: 'note', body: document.getElementById('tnote').value.trim(), actor: user.id })).then(function () { store('cs_thread', t.id); A.go('change'); });
          }).catch(fail);
        });
      }).catch(fail);
    });
  };
  // On a synthetic project an admin may act for any party (demo rule in the database); otherwise you are your party.
  function actingParty(cur) { return cur.synthetic && cur.is_admin ? (store('cs_acting') || cur.party) : cur.party; }

  /* ---------- one change: the shared thread ---------- */
  V.change = function () {
    gate(function () {
      var cur = proj(), id = store('cs_thread'); if (!cur || !id) return A.go('changes');
      Promise.all([q(sb.from('threads').select('*').eq('id', id).single()), q(sb.from('events').select('*').eq('thread_id', id).order('id')), q(sb.rpc('project_people', { p: cur.id }))]).then(function (r) {
        var t = r[0], evs = r[1]; people = {}; r[2].forEach(function (m) { people[m.user_id] = m; });
        var me = actingParty(cur), open = !/approved|rejected|withdrawn/.test(t.status), mine = open && t.holder === me;
        var returns = evs.filter(function (e) { return e.kind === 'return'; }).length;
        var acting = cur.synthetic && cur.is_admin ? '<div class="fd" style="max-width:260px"><label><span>Acting as (synthetic project only)</span></label><div class="inp sel"><select id="acting">' + Object.keys(PARTY).map(function (k) { return '<option value="' + k + '"' + (k === me ? ' selected' : '') + '>' + PARTY[k] + '</option>'; }).join('') + '</select></div></div>' : '';
        var actions = !open ? '<p style="margin:0">This change is ' + esc(STATUS[t.status].toLowerCase()) + '.</p>' : !mine ? '<p style="margin:0;color:var(--muted)">It’s with the ' + esc(PARTY[t.holder]) + '. You can comment.</p>' :
          '<div class="acts" style="margin:0 0 12px;flex-wrap:wrap">' + (NEXT[me] ? '<button class="btn primary" data-tact="submit">Send to ' + esc(PARTY[NEXT[me]]) + '</button>' : '') + (me === 'owner' ? '<button class="btn primary" data-tact="approve">Approve</button><button class="btn" data-tact="reject">Reject</button>' : '') + (PREV[me] ? '<button class="btn" data-tact="return">Return to ' + esc(PARTY[PREV[me]]) + '</button>' : '') + '</div>' +
            (me !== 'owner' ? '<div class="acts" style="margin:0 0 12px;flex-wrap:wrap"><button class="btn sm" data-tact="draft">Draft the formal proposal from the record</button><button class="btn sm" data-tact="check">Run the contract checks</button></div>' : '<div class="acts" style="margin:0 0 12px"><button class="btn sm" data-tact="check">Run the contract checks</button></div>') +
            '<div class="fd" id="reasonbox" hidden><label><span>Why it’s going back</span></label><div class="inp sel"><select id="treason">' + REASONS.map(function (x) { return '<option value="' + x[0] + '">' + x[1] + '</option>'; }).join('') + '</select></div></div>';
        var tl = evs.map(function (e) {
          var who = people[e.actor];
          return '<li class="ev ' + e.kind + '"><div class="ev-h"><span class="who ' + ((e.payload && e.payload.built_by === 'ai') ? 'ai' : (e.kind === 'check' || e.kind === 'draft') ? 'computed' : 'person') + '">' + esc(PARTY[e.party]) + '</span><b>' + esc(KIND[e.kind] || e.kind) + '</b>' + (e.reason ? '<span class="tagr chk">' + esc((REASONS.filter(function (x) { return x[0] === e.reason; })[0] || [0, e.reason])[1]) + '</span>' : '') + '<span class="fine">' + when(e.created_at) + (who && who.email ? ' · ' + esc(who.email) : '') + '</span></div>' +
            (e.body ? '<p>' + esc(e.body) + '</p>' : '') + '</li>';
        }).join('');
        app.innerHTML = sheet(t.title, 'T-201 · ' + t.number + ' · ' + cur.name,
          '<p style="margin:-6px 0 16px;color:var(--muted)"><span class="badge' + (t.status === 'approved' ? ' ok' : t.status === 'returned' ? ' fail' : '') + '">' + esc(STATUS[t.status]) + '</span> ' + (open ? 'With the ' + esc(PARTY[t.holder]) + '.' : '') + ' ' + returns + ' return' + (returns === 1 ? '' : 's') + ' so far. <a class="link" href="#changes">All changes</a></p>' +
          '<div class="cols" style="grid-template-columns:minmax(0,1.5fr) minmax(0,1fr)"><div class="card sec"><div class="sec-h"><h3>Thread</h3><span class="fine" style="margin:0">Every entry is permanent.</span></div><ol class="timeline">' + tl + '</ol></div>' +
          '<div><div class="card sec">' + acting + actions + '<div class="fd" style="margin-top:10px"><label><span>' + (mine ? 'Note to send with it' : 'Comment') + '</span></label><div class="inp" style="height:auto"><textarea id="tbody" rows="4"></textarea></div></div>' +
          '<div class="acts" style="margin-top:10px"><button class="btn" data-tact="comment">Add comment</button></div></div>' +
          '<div class="card sec" style="margin-top:16px"><div class="sec-h"><h3>Evidence trail</h3></div><div id="trail"><p class="fine" style="margin:0">Building from the record…</p></div></div></div></div>');
        trail(cur, t).then(function (tr) { var el = document.getElementById('trail'); if (el) el.innerHTML = trailHtml(tr); }).catch(function (e) { var el = document.getElementById('trail'); if (el) el.innerHTML = '<p class="fine">' + esc(e.message) + '</p>'; });
        var sel = document.getElementById('acting'); if (sel) sel.addEventListener('change', function () { store('cs_acting', sel.value); V.change(); });
        app.querySelectorAll('[data-tact]').forEach(function (b) {
          b.addEventListener('click', function () {
            var k = b.dataset.tact, body = (document.getElementById('tbody').value || '').trim(), box = document.getElementById('reasonbox');
            if (k === 'return' && box && box.hidden) { box.hidden = false; b.textContent = 'Confirm return'; return; }
            if (k === 'comment' && !body) return A.toast('Write a comment first.');
            if (k === 'check') return runChecks(cur, t, me).then(function () { A.toast('Checks saved to the thread.'); V.change(); }).catch(fail);
            if (k === 'aidraft') {
              var note2 = (evs.filter(function (x) { return x.kind === 'note'; })[0] || {}).body || '';
              var get = A.reader() ? fetch('/api/draft', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ note: note2, exclude: [t.number] }) }).then(function (r) { return r.json(); })
                : fetch('/record/results/draft_llama3.1_8b.json').then(function (r) { if (!r.ok) throw new Error('No saved AI run yet; it is being produced on GitHub.'); return r.json(); }).then(function (j) { var row = j.rows.filter(function (x) { return x.id === t.number && x.variant === 'plain'; })[0]; if (!row) throw new Error('No saved AI run for ' + t.number + '.'); return { draft: { scope: row.scope }, cause: row.cause ? { doc: row.cause } : null, governing: (row.governing || []).map(function (g) { return { id: g }; }), notes: row.notes || [], model: j.meta.model + ' (saved run ' + j.meta.date + ')' }; });
              return get.then(function (res) {
                if (res.error) throw new Error(res.error);
                var body = 'Scope: ' + (res.draft.scope || '') + '\nCause cited: ' + (res.cause ? (res.cause.number || res.cause.doc) + (res.cause.section ? ' ' + res.cause.section : '') : 'none') + '\nGoverning: ' + ((res.governing || []).map(function (g) { return g.id.replace('|', ' § '); }).join('; ') || 'none') + (res.notes && res.notes.length ? '\nCode flagged: ' + res.notes.join(' ') : '\nCode found nothing to flag.') + '\nDrafted by ' + res.model + '; it could only cite entries from the record.';
                return q(sb.from('events').insert({ thread_id: t.id, project_id: cur.id, party: me, kind: 'draft', body: body, payload: { built_by: 'ai', model: res.model }, actor: user.id }));
              }).then(function () { A.toast('AI draft added. Confirm or edit before sending.'); V.change(); }).catch(fail);
            }
            if (k === 'draft') {
              var note = (evs.filter(function (x) { return x.kind === 'note'; })[0] || {}).body || '';
              return trail(cur, t).then(function (tr) { return q(sb.from('events').insert({ thread_id: t.id, project_id: cur.id, party: me, kind: 'draft', body: draftText(tr, t, note), payload: { built_by: 'code', sources: tr ? tr.links.length : 0 }, actor: user.id })); })
                .then(function () { A.toast('Draft added. Every line cites the record.'); V.change(); }).catch(fail);
            }
            var row = { thread_id: t.id, project_id: cur.id, party: me, kind: k, body: body || null, actor: user.id };
            if (k === 'return') row.reason = document.getElementById('treason').value;
            q(sb.from('events').insert(row)).then(function () { A.toast(k === 'submit' ? 'Sent to the ' + PARTY[NEXT[me]] + '.' : k === 'return' ? 'Returned with a reason.' : k === 'approve' ? 'Approved.' : 'Saved.'); V.change(); }).catch(fail);
          });
        });
      }).catch(fail);
    });
  };

  /* ---------- evidence trail: what led to this change, built by code from the record's links ---------- */
  var REL = { caused_by: 'Caused by', answered_by: 'Answered by', evidence_for: 'Site record', discussed: 'Discussed at', cites: 'Governed by', affects: 'Schedule work', supersedes: 'Changes' };
  function trail(cur, t) {
    if (!t.document_id) return Promise.resolve(null);
    var co = t.document_id;
    return q(sb.from('links').select('*').eq('project_id', cur.id).or('from_doc.eq.' + co + ',to_doc.eq.' + co)).then(function (l1) {
      var causes = l1.filter(function (l) { return l.from_doc === co && l.relation === 'caused_by'; }).map(function (l) { return l.to_doc; });
      var hop = causes.length ? q(sb.from('links').select('*').eq('project_id', cur.id).in('from_doc', causes)) : Promise.resolve([]);
      var hop2 = causes.length ? q(sb.from('links').select('*').eq('project_id', cur.id).in('to_doc', causes)) : Promise.resolve([]);
      return Promise.all([hop, hop2]).then(function (r) {
        var all = l1.concat(r[0].filter(function (l) { return /answered_by|cites/.test(l.relation); }), r[1].filter(function (l) { return l.relation === 'discussed'; }));
        var docIds = {}, pieceIds = {};
        all.forEach(function (l) { [l.from_doc, l.to_doc].forEach(function (d) { if (d) docIds[d] = 1; }); [l.from_piece, l.to_piece].forEach(function (p) { if (p) pieceIds[p] = 1; }); });
        return Promise.all([q(sb.from('documents').select('id,kind,number,title,issued_on,author_party').in('id', Object.keys(docIds))), Object.keys(pieceIds).length ? q(sb.from('pieces').select('id,section,body,piece_date,party').in('id', Object.keys(pieceIds))) : Promise.resolve([])])
          .then(function (d) { var D = {}, P = {}; d[0].forEach(function (x) { D[x.id] = x; }); d[1].forEach(function (x) { P[x.id] = x; }); return { links: all, D: D, P: P, co: co }; });
      });
    });
  }
  function trailHtml(tr) {
    if (!tr) return '<p class="fine" style="margin:0">This change isn’t tied to a change order document in the record yet.</p>';
    var events = [], governs = [], work = [], seen = {};
    tr.links.forEach(function (l) {
      var other = l.from_doc === tr.co ? l.to_doc : l.to_doc === tr.co ? l.from_doc : (l.relation === 'answered_by' ? l.to_doc : l.from_doc);
      var piece = tr.P[l.from_doc === other ? l.from_piece : l.to_piece] || null, d = tr.D[other]; if (!d) return;
      var k = other + '|' + (piece ? piece.id : '') + '|' + l.relation; if (seen[k]) return; seen[k] = 1;
      var item = { d: d, piece: piece, rel: l.relation, date: (piece && piece.piece_date) || d.issued_on || '' };
      if (l.relation === 'cites') governs.push(item); else if (l.relation === 'affects') work.push(item); else events.push(item);
    });
    events.sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
    function li(x) {
      return '<li class="ev"><div class="ev-h"><span class="who computed">' + esc(REL[x.rel] || x.rel) + '</span><b><button class="link" data-dopen="' + x.d.id + '">' + esc(x.d.number || x.d.title) + '</button></b>' + (x.piece && x.piece.section ? '<span class="fine">' + esc(x.piece.section) + '</span>' : '') + '<span class="fine">' + esc(x.date) + (x.d.author_party ? ' · ' + esc(PARTY[x.d.author_party]) : '') + '</span></div>' +
        (x.piece ? '<p class="quote-line">“' + esc(x.piece.body.length > 260 ? x.piece.body.slice(0, 257) + '…' : x.piece.body) + '”</p>' : '<p>' + esc(x.d.title) + '</p>') + '</li>';
    }
    return (events.length ? '<ol class="timeline">' + events.map(li).join('') + '</ol>' : '<p class="fine">No events linked yet.</p>') +
      (governs.length ? '<div class="sec-h" style="margin-top:16px"><h3>Terms that govern it</h3></div><ul class="govern">' + governs.map(function (x) { return '<li><button class="link" data-dopen="' + x.d.id + '">' + esc(x.d.number || x.d.title) + (x.piece && x.piece.section ? ' § ' + esc(x.piece.section) : '') + '</button>' + (x.piece ? '<span>' + esc(x.piece.body.length > 140 ? x.piece.body.slice(0, 137) + '…' : x.piece.body) + '</span>' : '') + '</li>'; }).join('') + '</ul>' : '') +
      (work.length ? '<p class="fine" style="margin-top:12px">Schedule work affected: ' + work.map(function (x) { return esc(x.piece ? x.piece.section : x.d.number); }).join(', ') + '. <a class="link" href="#delay">Check the delay</a></p>' : '') +
      '<p class="fine" style="margin-top:12px">Built by code from the record’s links; every line points to its source. Who is responsible is for the parties to decide.</p>';
  }

  /* ---------- checks and draft at the handoff ---------- */
  var caseIndex = null;
  function findCase(number) {
    if (!caseIndex) caseIndex = Promise.all(['/demo3/data/cases.json', '/demo4/data/cases.json'].map(function (u) { return fetch(u).then(function (r) { return r.ok ? r.json() : { cases: [] }; }).catch(function () { return { cases: [] }; }); }))
      .then(function (r) { var o = {}; r.forEach(function (j) { (j.cases || []).forEach(function (c) { o[c.id] = c; }); }); return o; });
    return caseIndex.then(function (o) { return o[number] || null; });
  }
  function runChecks(cur, t, me) {
    return findCase(t.number).then(function (c) {
      if (!c) throw new Error('No priced cover sheet for ' + t.number + ' yet. Price it in Check a proposal first.');
      var K = window.ClauseChecks, cs = K.checksheet(c, A.C()), v = K.verdict(cs, me === 'owner' ? 'owner' : 'gc'), n = cs.counts;
      var fails = cs.rows.filter(function (r) { return r.status === 'fail'; }).map(function (r) { return '§ ' + r.section + ': ' + K.plain(r, me === 'owner' ? 'owner' : 'gc', A.C()).title; });
      var body = v.head.replace(/<[^>]+>/g, '') + '. ' + n.pass + ' checks passed, ' + n.fail + ' to fix, ' + n.person + ' for a person.' + (cs.dollars_at_issue > 0 ? ' ' + K.money(cs.dollars_at_issue) + ' at issue.' : '') + (fails.length ? '\n' + fails.join('\n') : '') + '\nChecked against ' + A.C().name + '.';
      return q(sb.from('events').insert({ thread_id: t.id, project_id: cur.id, party: me, kind: 'check', body: body, payload: { counts: n, dollars_at_issue: cs.dollars_at_issue, contract: A.C().name, case: c.id }, actor: user.id }));
    });
  }
  function draftText(tr, t, note) {
    var lines = ['Change proposal ' + t.number + ': ' + t.title, ''];
    if (note) lines.push('Requested by the sub: ' + note, '');
    if (tr) {
      var cause = [], gov = [];
      tr.links.forEach(function (l) {
        var other = l.from_doc === tr.co ? l.to_doc : l.from_doc, d = tr.D[other], p = tr.P[l.from_doc === tr.co ? l.to_piece : l.from_piece];
        if (!d) return;
        if (l.relation === 'caused_by') cause.push('Cause: ' + (d.number || d.title) + (p && p.section ? ' (' + p.section + ')' : '') + (p ? ': “' + p.body.slice(0, 220) + (p.body.length > 220 ? '…' : '') + '”' : '') + ' [' + (d.number || d.title) + (p && p.section ? ' ' + p.section : '') + ']');
        if (l.relation === 'cites' && p) gov.push((d.number || d.title) + ' § ' + p.section);
      });
      lines = lines.concat(cause.length ? cause : ['Cause: not linked in the record yet. Add the RFI, ASI or field report before sending.']);
      if (gov.length) lines.push('', 'Priced and noticed under: ' + gov.filter(function (x, i) { return gov.indexOf(x) === i; }).join('; ') + '.');
    }
    lines.push('', 'Pricing: from the priced cover sheet in Check a proposal. Every line above cites its source in the record.');
    return lines.join('\n');
  }

  var KINDNAME = { rfi: 'RFI', asi: 'ASI', submittal: 'Submittal', daily_report: 'Daily report', minutes: 'Approved minutes', contract: 'Contract', spec: 'Spec section', change_order: 'Change order', other: 'Other' };
  // Split a document into quotable pieces. Contracts and specs by section number; RFIs by Question / Answer headings;
  // everything else by paragraph. Same idea as the synthetic record, so real documents land in the same shape.
  function splitPieces(kind, text, date, party) {
    var out = [];
    if (kind === 'contract' || kind === 'spec') {
      var CT = window.ClauseContract, by = {}, order = [];
      CT.sentences(text).forEach(function (x) { var k = x.section || '—'; if (!by[k]) { by[k] = []; order.push(k); } by[k].push(x.text); });
      order.forEach(function (k, i) { out.push({ ordinal: i + 1, section: k === '—' ? null : k, body: by[k].join(' '), piece_date: date || null, party: party }); });
      return out;
    }
    var sec = null, buf = [];
    function flush() { var b = buf.join(' ').replace(/\s+/g, ' ').trim(); if (b) out.push({ ordinal: out.length + 1, section: sec, body: b, piece_date: date || null, party: party }); buf = []; }
    String(text).split(/\r?\n/).forEach(function (line) {
      var m = line.match(/^\s*(?:#+\s*)?(question|answer|response|suggested solution|description|action|reviewer comments?|weather|crew counts?|work performed|issues?(?:\/delays)?|item\s+[\d.]+)\s*[:.-]\s*(.*)$/i);
      if (m) { flush(); sec = m[1].replace(/^\w/, function (c) { return c.toUpperCase(); }); if (m[2]) buf.push(m[2]); return; }
      if (!line.trim()) { flush(); return; }
      buf.push(line.trim());
    });
    flush();
    return out;
  }
  function upload(cur) {
    var f = document.getElementById('ufile').files[0], kind = document.getElementById('ukind').value;
    if (kind === 'minutes' && !document.getElementById('usub').checked) return A.toast('Only approved minutes go in the record. Tick the box once they’re approved.');
    var date = document.getElementById('udate').value || null, party = document.getElementById('uparty').value;
    var read = /\.pdf$/i.test(f.name) ? A.pdfText(f) : f.text();
    read.then(function (text) {
      if (text.replace(/\s/g, '').length < 40) throw new Error('No readable text in ' + f.name + '. A scanned PDF has no text layer.');
      var doc = { key: 'up:' + Date.now(), kind: kind, number: document.getElementById('unum').value.trim() || null, title: document.getElementById('utitle').value.trim(), issued_on: date, author_party: party, source: 'upload', external_id: 'up:' + f.name + ':' + f.size, meta: { file_name: f.name }, pieces: splitPieces(kind, text, date, party) };
      var path = cur.id + '/' + Date.now() + '-' + f.name.replace(/[^\w.-]+/g, '_');
      var store1 = sb.storage ? sb.storage.from('documents').upload(path, f).then(function (r) { if (!r.error) doc.meta.file_path = path; }) : Promise.resolve();
      return store1.then(function () { return importBundle(cur.id, { documents: [doc], links: [] }, function () {}); }).then(function () { A.toast('Added ' + (doc.number || doc.title) + ': ' + doc.pieces.length + ' pieces.'); V.record(); });
    }).catch(fail);
  }

  /* ---------- R-101 Record: search every piece, open any document ---------- */
  V.record = function () {
    gate(function () {
      var cur = proj(); if (!cur) return A.go('project');
      q(sb.from('documents').select('id,kind').eq('project_id', cur.id)).then(function (docs) {
        var counts = {}; docs.forEach(function (d) { counts[d.kind] = (counts[d.kind] || 0) + 1; });
        var qv = store('cs_rq') || '';
        app.innerHTML = sheet('Project record', 'R-101 · ' + cur.name, '<p style="margin:-6px 0 16px;color:var(--muted)">' + docs.length + ' document' + (docs.length === 1 ? '' : 's') + (docs.length ? ': ' + Object.keys(counts).map(function (k) { return counts[k] + ' × ' + (KINDNAME[k] || k); }).join(', ') : '') + '. Answers below are quoted from the record, never written by AI.</p>' +
          '<form id="rsearch" class="grid" style="grid-template-columns:minmax(0,1fr) auto;gap:10px;max-width:760px"><div class="inp"><input id="rq" value="' + esc(qv) + '" placeholder="Ask or search, e.g. roof drains, notice for concealed conditions, asbestos mastic"></div><button class="btn primary" type="submit">Search the record</button></form>' +
          '<div class="cols" style="grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);margin-top:18px"><div id="rres"><div class="card sec"><p style="margin:0;color:var(--muted)">Search finds the exact sentences in the RFIs, ASIs, submittals, daily reports, approved minutes, contract and specs. Each result links to its document and what it’s tied to.</p></div></div>' +
          '<div><div class="card sec"><div class="sec-h"><h3>Add a document</h3></div><form id="rup" class="grid"><div class="fd"><label><span>Kind</span></label><div class="inp sel"><select id="ukind">' +
          ['rfi', 'asi', 'submittal', 'daily_report', 'minutes', 'contract', 'spec', 'change_order', 'other'].map(function (k) { return '<option value="' + k + '">' + KINDNAME[k] + '</option>'; }).join('') + '</select></div></div>' +
          '<div class="fd"><label><span>Number</span></label><div class="inp"><input id="unum" placeholder="e.g. RFI-241"></div></div>' +
          '<div class="fd full"><label><span>Title</span></label><div class="inp"><input id="utitle" required></div></div>' +
          '<div class="fd"><label><span>Dated</span></label><div class="inp"><input id="udate" type="date"></div></div>' +
          '<div class="fd"><label><span>From the</span></label><div class="inp sel"><select id="uparty">' + Object.keys(PARTY).map(function (k) { return '<option value="' + k + '">' + PARTY[k] + '</option>'; }).join('') + '</select></div></div>' +
          '<div class="fd full"><label><span>File (PDF with text, .txt or .md)</span></label><input id="ufile" type="file" accept=".pdf,.txt,.md" required></div>' +
          '<div class="fd full"><label class="tog-row"><input type="checkbox" id="usub"> Approved meeting minutes only: these minutes were approved at a later meeting</label></div>' +
          '<div class="fd full"><button class="btn primary" type="submit">Add to the record</button></div></form>' +
          '<p class="fine" style="margin:10px 0 0">The document is split into quotable pieces (by section, question and answer, or paragraph). Unapproved minutes aren’t accepted.</p></div>' +
          '<div class="card sec" style="margin-top:16px"><div class="sec-h"><h3>Procore</h3><span class="tagr none">not connected</span></div><p class="fine" style="margin:0">RFIs and change orders will sync from Procore through this same import once the project’s Procore developer account exists. Each synced item keeps its Procore id, so a re-sync updates instead of duplicating.</p></div></div></div>');
        document.getElementById('rup').addEventListener('submit', function (e) { e.preventDefault(); upload(cur); });
        document.getElementById('rsearch').addEventListener('submit', function (e) { e.preventDefault(); search(cur, document.getElementById('rq').value.trim()); });
        if (qv) search(cur, qv);
      }).catch(fail);
    });
  };
  function search(cur, text) {
    store('cs_rq', text); var el = document.getElementById('rres'); if (!text) { el.innerHTML = ''; return; }
    el.innerHTML = '<p class="fine">Searching…</p>';
    q(sb.from('pieces').select('id,document_id,section,body,piece_date,party').eq('project_id', cur.id).textSearch('search', text, { type: 'websearch', config: 'english' }).limit(12)).then(function (ps) {
      if (!ps.length) { el.innerHTML = '<div class="card sec"><p style="margin:0">Not found in the record. Try fewer or different words. ClauseStream won’t answer from outside the record.</p></div>'; return; }
      var ids = {}; ps.forEach(function (p) { ids[p.document_id] = 1; });
      return q(sb.from('documents').select('id,kind,number,title,issued_on').in('id', Object.keys(ids))).then(function (ds) {
        var D = {}; ds.forEach(function (d) { D[d.id] = d; });
        el.innerHTML = '<ol class="hits">' + ps.map(function (p) { var d = D[p.document_id] || {}; return '<li><div class="ev-h"><span class="who computed">' + esc((d.kind || '').replace('_', ' ')) + '</span><b><button class="link" data-dopen="' + p.document_id + '">' + esc(d.number || d.title) + '</button></b>' + (p.section ? '<span class="fine">' + esc(p.section) + '</span>' : '') + '<span class="fine">' + esc(p.piece_date || d.issued_on || '') + '</span></div><p>“' + esc(p.body) + '”</p></li>'; }).join('') + '</ol>';
      });
    }).catch(fail);
  }
  V.doc = function () {
    gate(function () {
      var cur = proj(), id = store('cs_doc'); if (!cur || !id) return A.go('record');
      Promise.all([q(sb.from('documents').select('*').eq('id', id).single()), q(sb.from('pieces').select('*').eq('document_id', id).order('ordinal')), q(sb.from('links').select('*').eq('project_id', cur.id).or('from_doc.eq.' + id + ',to_doc.eq.' + id))]).then(function (r) {
        var d = r[0], ps = r[1], ls = r[2], others = {};
        ls.forEach(function (l) { others[l.from_doc === id ? l.to_doc : l.from_doc] = 1; });
        return (Object.keys(others).length ? q(sb.from('documents').select('id,number,title,kind').in('id', Object.keys(others))) : Promise.resolve([])).then(function (od) {
          var O = {}; od.forEach(function (x) { O[x.id] = x; });
          var rel = ls.map(function (l) { var out = l.from_doc === id, o = O[out ? l.to_doc : l.from_doc] || {}; return '<li><span class="fine">' + esc(out ? (REL[l.relation] || l.relation) : 'Referenced by (' + l.relation.replace('_', ' ') + ')') + '</span> <button class="link" data-dopen="' + o.id + '">' + esc(o.number || o.title || '') + '</button></li>'; }).join('');
          app.innerHTML = sheet((d.number ? d.number + ' ' : '') + d.title, 'R-101 · ' + d.kind.replace('_', ' ') + (d.source === 'synthetic' ? ' · synthetic' : ''),
            '<p style="margin:-6px 0 16px;color:var(--muted)">' + esc(d.issued_on || '') + (d.author_party ? ' · from the ' + esc(PARTY[d.author_party]) : '') + '. <a class="link" href="#record">Back to the record</a></p>' +
            '<div class="cols" style="grid-template-columns:minmax(0,1.6fr) minmax(0,1fr)"><div class="card sec"><ol class="pieces">' + ps.map(function (p) { return '<li><span class="fine">' + esc(p.section || p.ordinal) + '</span><p>' + esc(p.body) + '</p></li>'; }).join('') + '</ol></div>' +
            '<div class="card sec"><div class="sec-h"><h3>Linked</h3></div>' + (rel ? '<ul class="govern">' + rel + '</ul>' : '<p class="fine" style="margin:0">Nothing linked.</p>') + '</div></div>');
        });
      }).catch(fail);
    });
  };

  app.addEventListener('click', function (e) {
    var t = e.target.closest('[data-popen],[data-signout],[data-loadsample],[data-topen],[data-dopen]'); if (!t) return;
    if (t.dataset.dopen) { store('cs_doc', t.dataset.dopen); return A.go('doc'); }
    if (t.dataset.signout) { sb.auth.signOut().then(function () { setProj(null); V.project(); }); return; }
    if (t.dataset.loadsample) { e.preventDefault(); return loadSample(); }
    if (t.dataset.topen) { store('cs_thread', t.dataset.topen); return A.go('change'); }
    if (t.dataset.popen) {
      Promise.all([q(sb.from('projects').select('id,name,synthetic').eq('id', t.dataset.popen).single()), q(sb.from('members').select('party,is_admin').eq('project_id', t.dataset.popen).eq('user_id', user.id).single())])
        .then(function (r) { setProj(Object.assign(r[0], r[1])); V.project(); }).catch(fail);
    }
  });
  app.addEventListener('submit', function (e) {
    if (e.target.id !== 'newp') return; e.preventDefault();
    createProject(document.getElementById('pname').value.trim(), document.getElementById('pparty').value, false).then(function () { A.toast('Project created. Invite the other parties.'); V.project(); }).catch(fail);
  });
  V.importBundle = importBundle; V.sb = function () { return sb; }; V.connect = connect;
  if (/[?&](signin=1|code=)/.test(location.search)) connect();
})();
