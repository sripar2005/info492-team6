/* ClauseStream quick check: upload -> confirm the numbers -> results. The full flow is the change thread (views-platform.js).
 * The checks themselves are in checks.js and run in the browser. Reading a PDF needs the local model
 * on the team's laptop (demo3/serve_local.py, POST /api/extract); everything else works anywhere. */
(function () {
  'use strict';
  var K = window.ClauseChecks, M = K.money;
  var app = document.getElementById('app');
  var ROLES = ['sub', 'gc', 'architect', 'owner'];
  var CAUSES = [['RFI response', 'An answer to an RFI'], ['ASI', "An architect's supplemental instruction (ASI)"], ['Submittal return', 'A returned submittal'],
    ['Owner direction', 'A direction from the owner'], ['Architect direction', 'A direction from the architect'], ['Concealed condition', 'A hidden site condition'], ['Other event', 'Something else']];
  var CAUSE_LABEL = {}; CAUSES.forEach(function (c) { CAUSE_LABEL[c[0]] = c[1]; });
  var FEE_LABEL = { 'CM direct costs': "CM's own work", 'subcontractor quotes': 'Subcontractor quotes', 'NSS items': 'Site services billed at cost (NSS)',
    'SGC items': 'General conditions items (SGC)', 'bond and insurance': 'Bond and insurance', 'B&O tax': 'B&O tax', 'permit fees': 'Permit fees', 'extended SGC (time)': 'Extended general conditions (time)' };
  var FEE_KEY = { 'NSS items': 'nss', 'SGC items': 'sgc', 'bond and insurance': 'bond', 'B&O tax': 'bo', 'permit fees': 'permits', 'extended SGC (time)': 'ext_sgc' };
  var SAMPLES = [['CP-0212', 'Haul-off with a fee problem'], ['CP-0201', 'A clean roof-drain change'], ['CP-0231', 'Plumbing quote sent by email']];

  var cases = {}, role = 'gc', S = null, reader = null, pdfjs = null;
  function store(k, v) { try { if (v === undefined) return JSON.parse(localStorage.getItem(k)); localStorage.setItem(k, JSON.stringify(v)); } catch (e) { return null; } }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function toast(t) { var el = document.getElementById('toast'); el.textContent = t; el.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(function () { el.hidden = true; }, 3600); }
  function num(v) { var x = parseFloat(String(v).replace(/[$,\s%]/g, '')); return isFinite(x) ? x : 0; }
  function fmt(x) { return x === 0 || x ? String(x) : ''; }
  // Revision triangle, drawn the way a delta tag is on a drawing: double outline, number inside.
  // kind: 'fail' red filled, 'person' amber outline (a person needs to look), 'nc' grey outline.
  function tag(n, kind, size) {
    size = size || 24; var w = size, h = Math.round(size * 0.88), i = size >= 22 ? 2.6 : 2.1, o = 0.8, fs = Math.round(size * 0.48);
    var outer = 'M' + (w / 2) + ' ' + o + ' L' + (w - o) + ' ' + (h - o) + ' L' + o + ' ' + (h - o) + ' Z';
    var inner = 'M' + (w / 2) + ' ' + (o + i * 1.9).toFixed(1) + ' L' + (w - o - i * 1.7).toFixed(1) + ' ' + (h - o - i).toFixed(1) + ' L' + (o + i * 1.7).toFixed(1) + ' ' + (h - o - i).toFixed(1) + ' Z';
    var ink = kind === 'fail' ? '#C8102E' : kind === 'nc' ? '#7A7A7A' : '#8A6100', fill = kind === 'fail' ? ink : '#FFFFFF', txt = kind === 'fail' ? '#FFFFFF' : ink;
    return '<svg class="dtag" role="img" aria-label="' + (kind === 'fail' ? 'Must fix ' : kind === 'person' ? 'For a person, ' : 'Not checked, ') + n + '" width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '">' +
      '<path d="' + outer + '" fill="' + fill + '" stroke="' + ink + '" stroke-width="1.6"/><path d="' + inner + '" fill="none" stroke="' + (kind === 'fail' ? '#FFFFFF' : ink) + '" stroke-width="0.9"' + (kind === 'nc' ? ' stroke-dasharray="2 1.5"' : '') + '/>' +
      '<text x="' + (w / 2) + '" y="' + (h - o - i - 2.2).toFixed(1) + '" text-anchor="middle" font-family="Barlow Condensed, Arial Narrow, sans-serif" font-weight="700" font-size="' + fs + '" fill="' + txt + '">' + n + '</text></svg>';
  }
  function uid() { return 'p' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }

  /* ---------- state ---------- */
  function blankSub() { return { firm: '', trade: '', email_only: false, own_cost: 0, own_markup_pct: 0, lower_cost: 0, lower_markup_pct: 0, breakdown: true, tm_tags: [] }; }
  function blankForm() { return { id: '', title: '', cause: '', cause_ref: '', event_date: '', notice_date: '', time_days: 0, subs: [blankSub()], cm_direct: 0, labor: [], equipment: [], _other_lines: [],
    nss: 0, sgc: 0, bond: 0, bo: 0, permits: 0, ext_sgc: 0, fee_pct: 0, fee_on: [], fee_amount: 0, total: 0, sub_total: 0 }; }
  function fillDefaults(f) {
    var b = blankForm(); Object.keys(b).forEach(function (k) { if (f[k] == null) f[k] = b[k]; });
    f.subs.forEach(function (s) { if (!s.email_only) { var d = blankSub(); Object.keys(d).forEach(function (k) { if (s[k] == null) s[k] = d[k]; }); } });
    return f;
  }
  // Keep the numbers as written. Totals follow edits unless the document's own total is off by more than $1.
  function settle(f) {
    var c = K.recompute(clone(f));
    f._sub_manual = Math.abs(c.sub_total - f.sub_total) > 1;
    f._fee_manual = Math.abs(c.fee_amount - f.fee_amount) > 1;
    f._total_manual = Math.abs(c.total - f.total) > 1;
    return f;
  }
  function retotal(f) {
    var c = K.recompute(clone(f));
    if (!f._sub_manual) f.sub_total = c.sub_total;
    var c2 = K.recompute(clone(f)); // fee depends on sub_total
    if (!f._fee_manual) f.fee_amount = K.round(c2.fee_amount, 2);
    var base = linesTotal(f);
    if (!f._total_manual) f.total = base;
    f._lines_total = base;
  }
  function linesTotal(f) { return K.round(num(f.cm_direct) + num(f.sub_total) + num(f.fee_amount) + num(f.bond) + num(f.bo) + num(f.permits) + num(f.nss) + num(f.sgc) + num(f.ext_sgc), 2); }
  function ready(f) { return f.cause && /^\d{4}-\d{2}-\d{2}$/.test(f.event_date) && /^\d{4}-\d{2}-\d{2}$/.test(f.notice_date); }
  function caseOf(f) { var c = K.toCase(f); c.id = f.id || 'Your proposal'; c.title = f.title || 'Change proposal'; return c; }
  function start(form, source, extra) {
    S = Object.assign({ form: fillDefaults(settle(form)), source: source, key: uid(), read: false, need: [], pdf: null, edited: false }, extra || {});
    saveSession();
  }
  function startSample(id) { start(K.toForm(cases[id]), 'sample', { sampleId: id }); }
  function saveSession() { try { sessionStorage.setItem('cs_current', JSON.stringify(Object.assign({}, S, { pdf: S && S.pdf ? { name: S.pdf.name } : null }))); } catch (e) {} }
  function loadSession() { try { var x = JSON.parse(sessionStorage.getItem('cs_current')); if (x && x.form) S = x; } catch (e) {} }

  /* ---------- role ---------- */
  function setRole(r) {
    role = ROLES.indexOf(r) >= 0 ? r : 'gc'; store('cs_role', role);
    document.querySelectorAll('#roles button').forEach(function (b) { b.setAttribute('aria-checked', b.dataset.role === role); });
  }
  document.getElementById('roles').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; setRole(b.dataset.role); route(); });

  /* ---------- views ---------- */
  function steps(n) {
    var names = ['Upload', 'Confirm the numbers', 'Results'], h = '<div class="steps">';
    names.forEach(function (t, i) {
      var cls = i + 1 < n ? 'done' : i + 1 === n ? 'on' : '';
      h += (i ? '<span class="bar"></span>' : '') + '<span class="st ' + cls + '"' + (cls === 'done' ? ' data-go="' + ['upload', 'confirm'][i] + '"' : '') + '><i>' + (cls === 'done' ? '✓' : i + 1) + '</i><span>' + t + '</span></span>';
    });
    return h + '</div>';
  }

  function viewUpload(err) {
    var R = K.ROLE[role], owner = role === 'owner' || role === 'architect';
    var lede = owner ? 'See what the contract allows before you approve it: markups, the CM fee, labor rates, equipment, deadlines and signatures.'
      : role === 'sub' ? 'Check your quote against the contract before you send it to the GC/CM.' : 'Check it against your contract before you send it. Takes about a minute.';
    app.innerHTML = '<div class="wrap">' + steps(1) + '<section class="upload"><h1>' + esc(R.q) + '</h1><p class="lede">' + lede + '</p>' +
      '<div class="drop" id="drop"><div class="ic"></div><b>Drop the change proposal here</b><p>PDF. We read it, you confirm the numbers, then we check them.</p>' +
      '<label class="btn primary">Choose a PDF<input type="file" accept="application/pdf,.pdf" id="file" hidden></label>' +
      '<span class="or">or <button class="link" data-act="manual">enter the numbers yourself</button></span>' +
      '<div class="reader ' + (reader ? 'on' : '') + '"><span class="dot"></span>' + (reader ? 'PDF reading is on: ' + esc(reader) + ' running on this computer' : 'PDF reading runs on the team’s laptop. Here, use a sample or enter the numbers.') + '</div></div>' +
      (err ? '<div class="err">' + esc(err) + '</div>' : '') +
      '<div class="samples">No file handy? Try a sample:' + SAMPLES.map(function (s) { return '<button data-sample="' + s[0] + '">' + esc(s[1]) + '</button>'; }).join('') + '</div>' +
      '<div class="checks">' + ['Subcontractor markups', 'CM fee', 'Labor rates', 'Equipment rates', 'Totals add up', 'Notice deadlines', 'Signed T&M tags', 'Approval limit'].map(function (x) { return '<span>' + x + '</span>'; }).join('') + '</div>' +
      '<p class="fine">Checks run in your browser. Nothing is sent to an outside AI service.</p></section></div>';
    var drop = document.getElementById('drop');
    ['dragenter', 'dragover'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('over'); }); });
    ['dragleave', 'drop'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('over'); }); });
    drop.addEventListener('drop', function (e) { var f = e.dataTransfer.files[0]; if (f) handleFile(f); });
    document.getElementById('file').addEventListener('change', function (e) { if (e.target.files[0]) handleFile(e.target.files[0]); });
  }

  /* ---------- PDF ---------- */
  function loadPdfjs() {
    if (pdfjs) return Promise.resolve(pdfjs);
    return new Promise(function (ok, no) {
      var s = document.createElement('script'); s.src = '/assets/vendor/pdfjs/pdf.min.js';
      s.onload = function () { pdfjs = window.pdfjsLib; pdfjs.GlobalWorkerOptions.workerSrc = '/assets/vendor/pdfjs/pdf.worker.min.js'; ok(pdfjs); };
      s.onerror = function () { no(new Error('Could not load the PDF viewer.')); }; document.head.appendChild(s);
    });
  }
  function handleFile(file) {
    if (!/\.pdf$/i.test(file.name) && file.type !== 'application/pdf') return viewUpload('That file isn’t a PDF. Only PDFs can be read for now; you can enter the numbers yourself.');
    app.innerHTML = '<div class="wrap"><div class="reading"><div class="spinner"></div><h2>Opening ' + esc(file.name) + '…</h2></div></div>';
    var pages = [], text = '';
    loadPdfjs().then(function (lib) { return file.arrayBuffer().then(function (buf) { return lib.getDocument({ data: buf }).promise; }); })
      .then(function (doc) {
        var jobs = [];
        for (var i = 1; i <= doc.numPages; i++) jobs.push(doc.getPage(i).then(function (pg) {
          return pg.getTextContent().then(function (tc) {
            var t = tc.items.map(function (it) { return it.str + (it.hasEOL ? '\n' : ' '); }).join('');
            if (pg.pageNumber <= 4) {
              var vp = pg.getViewport({ scale: 1.4 }), c = document.createElement('canvas'); c.width = vp.width; c.height = vp.height;
              return pg.render({ canvasContext: c.getContext('2d'), viewport: vp }).promise.then(function () { return { n: pg.pageNumber, t: t, c: c }; });
            }
            return { n: pg.pageNumber, t: t };
          });
        }));
        return Promise.all(jobs);
      })
      .then(function (res) {
        res.sort(function (a, b) { return a.n - b.n; });
        text = res.map(function (r) { return r.t; }).join('\n\n'); pages = res.filter(function (r) { return r.c; }).map(function (r) { return r.c; });
        var pdf = { name: file.name, canvases: pages };
        if (text.replace(/\s/g, '').length < 40) { start(blankForm(), 'manual', { pdf: pdf, banner: 'This PDF has no text layer (it looks scanned), so it can’t be read automatically. Enter the numbers below while looking at it on the left.' }); return go('confirm'); }
        if (!reader) { start(blankForm(), 'manual', { pdf: pdf, banner: 'Reading PDFs needs the local model, which runs on the team’s laptop. Enter the numbers below while looking at your file on the left.' }); return go('confirm'); }
        readWithModel(text, pdf);
      })
      .catch(function (e) { viewUpload('Could not open that PDF: ' + e.message); });
  }
  function readWithModel(text, pdf) {
    var t0 = Date.now(), cancelled = false;
    app.innerHTML = '<div class="wrap">' + steps(1) + '<div class="reading"><div class="spinner"></div><h2>Reading ' + esc(pdf.name) + '</h2><p class="fine" style="font-size:13.5px">' + esc(reader) +
      ' on this computer is copying the numbers into the form. Usually under two minutes. <span id="tick">0:00</span></p><p style="margin-top:18px"><button class="btn ghost sm" id="cancel">Enter the numbers myself instead</button></p></div></div>';
    var tick = setInterval(function () { var s = Math.round((Date.now() - t0) / 1000), el = document.getElementById('tick'); if (el) el.textContent = Math.floor(s / 60) + ':' + ('0' + s % 60).slice(-2); }, 1000);
    document.getElementById('cancel').onclick = function () { cancelled = true; clearInterval(tick); start(blankForm(), 'manual', { pdf: pdf }); go('confirm'); };
    fetch('/api/extract', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: text }) })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || 'HTTP ' + r.status); return j; }); })
      .then(function (j) {
        if (cancelled) return; clearInterval(tick);
        var f = fillDefaults(j.form); if (!f.subs.length) f.subs = [];
        start(f, 'pdf', { pdf: pdf, read: true, need: j.missing || [], secs: j.seconds, model: j.model });
        go('confirm');
      })
      .catch(function (e) { if (cancelled) return; clearInterval(tick); start(blankForm(), 'manual', { pdf: pdf, banner: 'The local model couldn’t read it (' + e.message + '). Enter the numbers below while looking at your file on the left.' }); go('confirm'); });
  }

  /* ---------- the document (left column) ---------- */
  function docLines(cp) {
    var c = cp.cover_sheet, L = [];
    cp.subcontractor_quotes.forEach(function (q, i) { L.push({ key: 'sub:' + i, label: 'Subcontractor: ' + (q.firm || 'unnamed') + (q.trade ? ' (' + q.trade + ')' : '') + (q.format === 'email text' ? ' · email quote' : ''), amt: q.quote_total }); });
    if (c.cm_direct_costs || cp.cm_lines.length) L.push({ key: 'cm', label: 'CM direct costs (labor, material, equipment)', amt: c.cm_direct_costs });
    [['nss', 'nss_items', 'Site services billed at cost (NSS)'], ['sgc', 'sgc_items', 'General conditions items (SGC)'], ['bond', 'bond_and_insurance', 'Bond and insurance'],
     ['bo', 'bo_tax', 'B&O tax'], ['permits', 'permit_fees', 'Permit fees'], ['ext_sgc', 'extended_sgc_time', 'Extended general conditions (time)']].forEach(function (x) { if (c[x[1]]) L.push({ key: x[0], label: x[2], amt: c[x[1]] }); });
    L.push({ key: 'fee', label: 'CM fee, ' + K.round(c.fee_rate * 100, 2) + '% on ' + (c.fee_applied_to.map(function (p) { var l = FEE_LABEL[p] || p; return /^[A-Z]{2}/.test(l) ? l : l.charAt(0).toLowerCase() + l.slice(1); }).join(', ') || '—'), amt: c.fee });
    L.push({ key: 'total', label: 'Total requested', amt: c.total_requested, tot: true });
    return L;
  }
  function shortNote(r, cp) {
    var d = r.difference > 0 ? ': ' + M(r.difference) : '';
    switch (r.flag) {
      case 'SUB_MARKUP': return 'markup over the limit' + d;
      case 'MISSING_BACKUP': return r.check.indexOf('T&M') >= 0 ? 'T&M tags not signed' : 'no breakdown attached';
      case 'TIEOUT': return r.check.indexOf('Cover') === 0 ? 'doesn’t add up: off by ' + M(Math.abs(r.difference)) : 'quote lines don’t add up';
      case 'FEE_RATE': return 'wrong fee rate' + d;
      case 'FEE_ON_EXCLUDED': return 'fee not allowed on part of this' + d;
      case 'LABOR_BURDEN': return 'labor burden over 32%' + d;
      case 'EQUIPMENT': return 'equipment over 75% of Blue Book';
      case 'LATE_NOTICE': return 'notice late';
      case 'TIME_IMPACT': return 'time claim: owner decides';
      case 'CONCEALED_CONDITION': return 'hidden condition: owner decides';
      case 'OVER_AUTHORITY': return 'over $250,000: higher approval';
    }
    return r.status === 'not_checked' ? 'email quote: not read' : r.check;
  }
  function lineFor(r, cp) {
    if (r.firm) { var i = cp.subcontractor_quotes.map(function (q) { return q.firm; }).indexOf(r.firm); return 'sub:' + i; }
    return { FEE_RATE: 'fee', FEE_ON_EXCLUDED: 'fee', LABOR_BURDEN: 'cm', EQUIPMENT: 'cm', OVER_AUTHORITY: 'total', TIEOUT: 'total',
      LATE_NOTICE: 'meta:notice', TIME_IMPACT: 'meta:time', CONCEALED_CONDITION: 'meta:cause' }[r.flag] || null;
  }
  function paperHtml(cp, findings, caption) {
    var marks = {};
    (findings || []).forEach(function (fd) {
      var k = lineFor(fd.r, cp); if (!k) return;
      (marks[k] = marks[k] || []).push({ n: fd.n, kind: fd.kind, text: shortNote(fd.r, cp) });
      if (fd.r.flag === 'FEE_ON_EXCLUDED') cp.cover_sheet.fee_applied_to.forEach(function (p) { var kk = FEE_KEY[p]; if (kk) (marks[kk] = marks[kk] || []).push({ n: fd.n, kind: 'fail', text: 'fee was charged on this', echo: true }); });
    });
    function note(k) { return (marks[k] || []).map(function (m) { return '<div><span class="num">' + tag(m.n, m.kind === 'fail' ? 'fail' : m.kind === 'person' ? 'person' : 'nc', 18) + '</span>' + esc(m.text) + '</div>'; }).join(''); }
    function ns(k) { var u = []; (marks[k] || []).forEach(function (m) { if (u.indexOf(m.n) < 0) u.push(m.n); }); return u.join(' '); }
    function kindOf(k) { var m = marks[k] || []; return m.some(function (x) { return x.kind === 'fail'; }) ? '' : m.some(function (x) { return x.kind === 'person'; }) ? ' person' : m.length ? ' nc' : ''; }
    var c = cp.cover_sheet, meta = [
      ['cause', CAUSE_LABEL[cp.cause.type] || cp.cause.type || 'Cause not set'], ['ref', cp.cause.reference], ['event', cp.cause.event_date ? 'Happened ' + cp.cause.event_date : ''],
      ['notice', cp.notice_date ? 'Notice given ' + cp.notice_date : ''], ['time', cp.time_impact_days ? cp.time_impact_days + ' days of time claimed' : '']];
    var metaNotes = ['cause', 'notice', 'time'].map(function (k) { return marks['meta:' + k] ? '<div style="color:' + (kindOf('meta:' + k) ? 'var(--amber)' : 'var(--red)') + '">' + note('meta:' + k) + '</div>' : ''; }).join('');
    var h = '<div class="paper"><div class="ph"><span class="eyebrow">' + esc(caption || 'Change proposal') + '</span><span class="eyebrow">' + esc(cp.id) + '</span></div>' +
      '<h3>' + esc(cp.title) + '</h3><div class="meta">' + meta.filter(function (m) { return m[1]; }).map(function (m) {
        var mk = marks['meta:' + m[0]]; return '<span' + (mk ? ' data-cloud="' + (kindOf('meta:' + m[0]).trim() || 'fail') + '" data-ns="' + ns('meta:' + m[0]) + '"' : '') + '>' + esc(m[1]) + '</span>'; }).join('') + '</div>' +
      (metaNotes ? '<div class="meta-notes">' + metaNotes + '</div>' : '') +
      '<div class="lines-lbl">Cover sheet</div><table class="doc' + (findings && findings.length ? '' : ' nonotes') + '"><tbody>' + docLines(cp).map(function (l) {
        var mk = marks[l.key]; return '<tr class="' + (l.tot ? 'tot ' : '') + (mk ? 'mk' + kindOf(l.key) : '') + (!mk && !l.amt && !l.tot ? ' dim' : '') + '"' + (mk ? ' data-cloud="' + (kindOf(l.key).trim() || 'fail') + '" data-ns="' + ns(l.key) + '"' : '') + '><td>' + esc(l.label) + '</td><td class="amt">' + M(l.amt || 0) + '</td><td class="note">' + note(l.key) + '</td></tr>';
      }).join('') + '</tbody></table>';
    var nf = (findings || []).filter(function (x) { return x.kind === 'fail'; }).length;
    h += '<div class="tblock"><div><span>Project</span><b>Sample school modernization</b></div><div><span>Change proposal</span><b>' + esc(cp.id) + '</b></div>' +
      '<div><span>Checked against</span><b>' + esc(C().name) + '</b></div><div><span>' + (findings ? 'Result' : 'Status') + '</span><b>' + (findings ? (nf ? nf + ' to fix' : 'Checks pass') : 'Not checked yet') + '</b></div></div>';
    return h + '</div>';
  }

  // Revision clouds: the scalloped outline used to mark changes on construction drawings.
  function cloudPath(x, y, w, h, r) {
    function edge(len) { var n = Math.max(2, Math.round(len / (r * 2))); return { n: n, s: len / n }; }
    var t = edge(w), v = edge(h), d = 'M' + x.toFixed(1) + ' ' + y.toFixed(1), i, a;
    for (i = 0; i < t.n; i++) { a = t.s * 0.62; d += ' a' + a + ' ' + a + ' 0 0 1 ' + t.s.toFixed(1) + ' 0'; }
    for (i = 0; i < v.n; i++) { a = v.s * 0.62; d += ' a' + a + ' ' + a + ' 0 0 1 0 ' + v.s.toFixed(1); }
    for (i = 0; i < t.n; i++) { a = t.s * 0.62; d += ' a' + a + ' ' + a + ' 0 0 1 ' + (-t.s).toFixed(1) + ' 0'; }
    for (i = 0; i < v.n; i++) { a = v.s * 0.62; d += ' a' + a + ' ' + a + ' 0 0 1 0 ' + (-v.s).toFixed(1); }
    return d + ' Z';
  }
  var COLORS = { fail: '#C8102E', person: '#B88700', nc: '#7A7A7A' };
  // Clouds go on a vellum layer over the drawing. They plot on once per render; a resize redraws them still.
  function drawClouds(plot) {
    document.querySelectorAll('.paper').forEach(function (paper) {
      var old = paper.querySelector('.vellum'); if (old) old.remove();
      var marked = paper.querySelectorAll('[data-cloud]'); if (!marked.length) return;
      var pb = paper.getBoundingClientRect(), k = 0, svg = '<svg class="clouds' + (plot === true ? ' plot' : '') + '" width="' + pb.width + '" height="' + pb.height + '" aria-hidden="true">';
      marked.forEach(function (el) {
        var b;
        if (el.tagName === 'TR') { var c = el.children, l = c[0].getBoundingClientRect(), rgt = c[1].getBoundingClientRect(); b = { left: l.left, top: l.top, right: rgt.right, bottom: l.bottom }; }
        else b = el.getBoundingClientRect();
        var pad = el.tagName === 'TR' ? 5 : 4, x = b.left - pb.left - pad - 4, y = b.top - pb.top + (el.tagName === 'TR' ? 9 : -pad), w = b.right - b.left + pad * 2 + 6, h = b.bottom - b.top + (el.tagName === 'TR' ? -18 : pad * 2);
        svg += '<path pathLength="1" style="animation-delay:' + (0.15 + 0.45 * k++) + 's" d="' + cloudPath(x, y, w, h, 6.5) + '" stroke="' + (COLORS[el.dataset.cloud] || COLORS.fail) + '"/>';
      });
      paper.insertAdjacentHTML('beforeend', '<div class="vellum" aria-hidden="true">' + svg + '</svg></div>');
    });
    zones();
  }
  // The zone frame around each sheet: letters across, numbers down, like a printed drawing.
  function frame() {
    var w = document.querySelector('#app > .wrap'); if (!w) return;
    var old = w.querySelector(':scope > .zf'); if (old) old.remove();
    var W = w.clientWidth, H = w.clientHeight, b = window.matchMedia('(max-width: 760px)').matches ? 14 : 22;
    var cols = W > 1000 ? 6 : W > 600 ? 4 : 3, rows = Math.max(2, Math.round((H - 2 * b) / 330)), cw = (W - 2 * b) / cols, rh = (H - 2 * b) / rows, h = '';
    for (var c = 0; c < cols; c++) {
      var L = String.fromCharCode(65 + c), x = b + cw * c;
      h += '<span style="left:' + x + 'px;top:0;width:' + cw + 'px;height:' + b + 'px">' + L + '</span><span style="left:' + x + 'px;bottom:0;width:' + cw + 'px;height:' + b + 'px">' + L + '</span>';
      if (c) h += '<i style="left:' + x + 'px;top:0;width:1px;height:' + b + 'px"></i><i style="left:' + x + 'px;bottom:0;width:1px;height:' + b + 'px"></i>';
    }
    for (var r = 0; r < rows; r++) {
      var y = b + rh * r;
      h += '<span style="top:' + y + 'px;left:0;width:' + b + 'px;height:' + rh + 'px">' + (r + 1) + '</span><span style="top:' + y + 'px;right:0;width:' + b + 'px;height:' + rh + 'px">' + (r + 1) + '</span>';
      if (r) h += '<i style="top:' + y + 'px;left:0;height:1px;width:' + b + 'px"></i><i style="top:' + y + 'px;right:0;height:1px;width:' + b + 'px"></i>';
    }
    w.insertAdjacentHTML('afterbegin', '<div class="zf" aria-hidden="true">' + h + '</div>');
    w._zone = { b: b, cols: cols, rows: rows, cw: cw, rh: rh };
  }
  function zoneRange(els) {
    var w = document.querySelector('#app > .wrap'), z = w && w._zone; if (!z || !els.length) return null;
    var wb = w.getBoundingClientRect(), bl = w.clientLeft, bt = w.clientTop, c0 = 99, c1 = -1, r0 = 99, r1 = -1;
    els.forEach(function (el) {
      var r = el.getBoundingClientRect(), cx = (r.left + r.right) / 2 - wb.left - bl, cy = (r.top + r.bottom) / 2 - wb.top - bt;
      var cA = Math.min(z.cols - 1, Math.max(0, Math.floor((r.left + 8 - wb.left - bl - z.b) / z.cw))), cB = Math.min(z.cols - 1, Math.max(0, Math.floor((r.right - 8 - wb.left - bl - z.b) / z.cw)));
      var row = Math.min(z.rows - 1, Math.max(0, Math.floor((cy - z.b) / z.rh)));
      c0 = Math.min(c0, cA); c1 = Math.max(c1, cB); r0 = Math.min(r0, row); r1 = Math.max(r1, row);
    });
    var name = function (c, r) { return String.fromCharCode(65 + c) + '-' + (r + 1); };
    return { c0: c0, c1: c1, r0: r0, r1: r1, label: c0 === c1 && r0 === r1 ? name(c0, r0) : name(c0, r0) + ' to ' + name(c1, r1), z: z };
  }
  function marksFor(n) { return Array.prototype.filter.call(document.querySelectorAll('.paper [data-ns]'), function (el) { return (' ' + el.dataset.ns + ' ').indexOf(' ' + n + ' ') >= 0; }); }
  function zones() {
    document.querySelectorAll('[data-zn]').forEach(function (chip) { var zr = zoneRange(marksFor(chip.dataset.zn)); if (zr) { chip.textContent = 'Zone ' + zr.label; chip.hidden = false; } else chip.hidden = true; });
  }
  function lightZone(n) {
    var w = document.querySelector('#app > .wrap'); if (!w) return; var old = w.querySelector('.zhl'); if (old) old.remove();
    if (n == null) return; var zr = zoneRange(marksFor(n)); if (!zr) return; var z = zr.z;
    w.insertAdjacentHTML('beforeend', '<div class="zhl" style="left:' + (z.b + z.cw * zr.c0) + 'px;top:' + (z.b + z.rh * zr.r0) + 'px;width:' + (z.cw * (zr.c1 - zr.c0 + 1)) + 'px;height:' + (z.rh * (zr.r1 - zr.r0 + 1)) + 'px"><b>' + esc(zr.label) + '</b></div>');
  }
  // Plain definitions for trade terms, shown on hover or focus the first time each term appears on a sheet.
  var GLOSS = [
    ['fragnet', 'The few new activities a change adds to the schedule, linked to existing work.'],
    ['critical path', 'The chain of work with no slack: if any of it slips, the finish date slips.'],
    ['float', 'How many days an activity can slip before it moves the finish date.'],
    ['data date', 'The date the schedule was last updated to; work before it is recorded, work after it is forecast.'],
    ['NSS', 'Negotiated support services: site costs the CM bills at cost, without fee.'],
    ['SGC', 'Specified general conditions: the CM’s site overhead (staff, trailer, utilities), usually a fixed amount.'],
    ['general conditions', 'The contractor’s site overhead for the time on site: staff, trailer, utilities, equipment.'],
    ['liquidated damages', 'A fixed amount per day the contractor owes if it finishes late, agreed in the contract.'],
    ['ASI', 'Architect’s supplemental instructions: a drawing or spec clarification issued by the architect.'],
    ['RFI', 'Request for information: a written question from the contractor that the architect answers.'],
    ['time impact analysis', 'Add the change’s work to the current schedule, recompute the critical path, and compare finish dates.'],
    ['Blue Book', 'The Rental Rate Blue Book: the industry reference for equipment hourly rates.']];
  function gloss() {
    var w = app.querySelector(':scope > .wrap'); if (!w || w.dataset.gl) return; w.dataset.gl = '1';
    var done = {}, walker = document.createTreeWalker(w, NodeFilter.SHOW_TEXT, { acceptNode: function (n) { return n.parentNode.closest('input,textarea,select,button,a,abbr,code,svg,.zf,.tblock,.stamp,h1') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT; } }), nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(function (n) {
      GLOSS.forEach(function (g) {
        if (done[g[0]] || !n.parentNode) return;
        var re = new RegExp('\\b' + g[0].replace(/ /g, '\\s') + '\\b', g[0] === g[0].toUpperCase() || g[0] === 'Blue Book' ? '' : 'i'), m = re.exec(n.nodeValue); if (!m) return;
        var after = n.splitText(m.index), rest = after.splitText(m[0].length), ab = document.createElement('abbr');
        ab.className = 'gl'; ab.tabIndex = 0; ab.dataset.def = g[1]; ab.textContent = after.nodeValue; after.parentNode.replaceChild(ab, after); done[g[0]] = 1; n = rest;
      });
    });
  }
  var fq = 0; function queueFrame() { if (fq) return; fq = requestAnimationFrame(function () { fq = 0; frame(); gloss(); }); }
  new MutationObserver(function () { var wr = app.querySelector(':scope > .wrap'); if (!app.querySelector(':scope > .wrap > .zf') || (wr && !wr.dataset.gl)) queueFrame(); }).observe(app, { childList: true });
  if (window.ResizeObserver) new ResizeObserver(queueFrame).observe(app);
  app.addEventListener('mouseover', function (e) { var li = e.target.closest('.fl > li[data-n]'); var cur = app.querySelector('.fl > li.hot'); if (cur === li) return; if (cur) cur.classList.remove('hot'); if (li) { li.classList.add('hot'); lightZone(li.dataset.n); } else lightZone(null); });
  app.addEventListener('focusin', function (e) { var li = e.target.closest('.fl > li[data-n]'); if (li) lightZone(li.dataset.n); });
  var rz; window.addEventListener('resize', function () { clearTimeout(rz); rz = setTimeout(function () { frame(); drawClouds(false); }, 120); });

  /* ---------- step 2: confirm ---------- */
  function field(path, label, val, opt) {
    opt = opt || {}; var need = S.need.indexOf(path) >= 0, tag = need ? '<span class="tagr chk">check this</span>' : S.read && val && opt.read !== false ? '<span class="tagr">read</span>' : '';
    var input;
    if (opt.select) input = '<div class="inp sel' + (need ? ' need' : '') + '"><select data-p="' + path + '"><option value="">Choose…</option>' + opt.select.map(function (o) { return '<option value="' + esc(o[0]) + '"' + (o[0] === val ? ' selected' : '') + '>' + esc(o[1]) + '</option>'; }).join('') + '</select></div>';
    else input = '<div class="inp' + (need ? ' need' : '') + '">' + (opt.pre ? '<span class="pre">' + opt.pre + '</span>' : '') + '<input data-p="' + path + '"' + (opt.type === 'date' ? ' type="date"' : opt.num ? ' inputmode="decimal" data-num="1"' : '') +
      ' value="' + esc(opt.num ? fmt(val) : val || '') + '"' + (opt.ph ? ' placeholder="' + esc(opt.ph) + '"' : '') + '>' + (opt.suf ? '<span class="suf">' + opt.suf + '</span>' : '') + '</div>';
    return '<div class="fd' + (opt.cls ? ' ' + opt.cls : '') + '"><label><span>' + label + (opt.small ? ' <small>' + opt.small + '</small>' : '') + '</span>' + tag + '</label>' + input + '</div>';
  }
  function subHtml(s, i) {
    var p = 'subs.' + i + '.', h = '<div class="subq"><div class="subq-h"><b>' + esc(s.firm || 'Subcontractor ' + (i + 1)) + '</b><button class="btn ghost sm" data-act="delsub" data-i="' + i + '">Remove</button></div><div class="grid">' +
      field(p + 'firm', 'Company', s.firm, { ph: 'e.g. Cascade Plumbing' }) + field(p + 'trade', 'Trade', s.trade, { ph: 'e.g. Plumbing', read: false });
    if (s.email_only) {
      h += field(p + 'quote_total', 'Quote total', s.quote_total, { num: true, pre: '$', cls: 'full' }) + '</div>' +
        '<div class="togs"><label class="tog"><input type="checkbox" data-p="' + p + 'email_only" checked> Quote came only as email text</label></div>' +
        (s.text ? '<div class="emailtxt">' + esc(s.text) + '</div>' : '') + '<p class="hint">Email quotes aren’t checked automatically. Turn this off to enter the quote’s numbers.</p></div>';
      return h;
    }
    h += field(p + 'own_cost', 'Their cost before markup', s.own_cost, { num: true, pre: '$' }) + field(p + 'own_markup_pct', 'Their markup on their own work', s.own_markup_pct, { num: true, suf: '%' }) +
      field(p + 'lower_cost', 'Lower-tier subs’ cost', s.lower_cost, { num: true, pre: '$', small: 'if any' }) + field(p + 'lower_markup_pct', 'Markup on lower-tier subs', s.lower_markup_pct, { num: true, suf: '%' }) + '</div>' +
      '<div class="togs"><label class="tog"><input type="checkbox" data-p="' + p + 'breakdown"' + (s.breakdown ? ' checked' : '') + '> Itemized breakdown attached</label>' +
      '<label class="tog"><input type="checkbox" data-p="' + p + 'email_only"> Quote came only as email text</label></div>' +
      '<div class="hint" style="margin-top:12px">Time-and-material tags · tick the ones signed by both the CM superintendent and the owner’s rep</div><div class="tags">' +
      (s.tm_tags || []).map(function (t, j) { return '<label><input type="checkbox" data-p="' + p + 'tm_tags.' + j + '.signed"' + (t.signed ? ' checked' : '') + '>' + esc(t.tag || 'Tag ' + (j + 1)) + '</label>'; }).join('') +
      '<button class="btn ghost sm" data-act="addtag" data-i="' + i + '">+ Tag</button></div>';
    return h + '<div class="hint">Quote total: ' + M(K.subTotal(s)) + '</div></div>';
  }
  function viewConfirm() {
    if (!S) return go('upload');
    var f = S.form, left;
    if (S.pdf && S.pdf.canvases) left = '<div class="paper"><div class="ph"><span class="eyebrow">Your file</span><span class="eyebrow">' + esc(S.pdf.name) + '</span></div><div class="pdfpages" id="pdfpages" style="margin-top:14px"></div><p class="paper-cap">Showing up to 4 pages.</p></div>';
    else left = ready(f) ? paperHtml(caseOf(f), null, S.source === 'sample' ? 'Sample proposal' : 'Change proposal') : '<div class="paper"><span class="eyebrow">Change proposal</span><p class="fine" style="font-size:13.5px">Fill in the cause and dates on the right to see the cover sheet here.</p></div>';
    var banner = S.banner ? '<div class="banner warn">' + esc(S.banner) + '</div>'
      : S.source === 'pdf' ? '<div class="banner"><span>We read <b>' + esc(S.pdf.name) + '</b> with ' + esc(S.model || 'the local model') + (S.secs ? ' in ' + Math.round(S.secs) + ' s' : '') + '. Fields marked <span class="tagr">read</span> came from the file; <span class="tagr chk">check this</span> means we couldn’t find it. The model can misread, so look before you check.</span></div>'
      : S.source === 'sample' ? '<div class="banner"><span><b>Sample proposal</b>, numbers as written. It’s synthetic, made for this project. Change anything to see how the result changes.</span></div>' : '';
    var heading = S.source === 'manual' ? 'Enter the proposal’s numbers' : 'Here’s what we read. Fix anything we got wrong.';
    var h = '<div class="wrap">' + steps(2) + '<div class="cols"><div>' + left + '</div><div class="form"><h2>' + heading + '</h2><p class="sub">Plain-language labels; the contract terms are in brackets.</p>' + banner +
      '<div class="card sec"><div class="sec-h"><h3>About the change</h3></div><div class="grid">' +
      field('title', 'Title', f.title, { cls: 'full', ph: 'e.g. Extra haul-off for abatement debris' }) +
      field('cause', 'What caused the change', f.cause, { select: CAUSES, cls: 'full' }) +
      field('event_date', 'Date it happened', f.event_date, { type: 'date' }) + field('notice_date', 'Date you gave written notice', f.notice_date, { type: 'date' }) +
      field('time_days', 'Extra days requested', f.time_days, { num: true, suf: 'days', small: '0 if none' }) + field('id', 'Proposal number', f.id, { ph: 'e.g. CP-0212', read: false }) + '</div></div>';
    h += '<div class="card sec"><div class="sec-h"><h3>Subcontractor quotes</h3><button class="btn ghost sm" data-act="addsub">+ Add a subcontractor</button></div>' +
      (f.subs.length ? f.subs.map(subHtml).join('') : '<p class="hint" style="margin:0">No subcontractor quotes.</p>') + '</div>';
    h += '<div class="card sec"><div class="sec-h"><h3>CM’s own costs</h3></div><div class="grid">' + field('cm_direct', 'CM’s own labor, material and equipment', f.cm_direct, { num: true, pre: '$', cls: 'full', small: 'cover-sheet total' }) + '</div>' +
      '<div class="hint" style="margin-top:12px">Labor lines, to check the labor burden</div>' + f.labor.map(function (l, i) {
        var p = 'labor.' + i + '.'; return '<div class="rowline">' + field(p + 'desc', 'Who', l.desc) + field(p + 'hours', 'Hours', l.hours, { num: true }) + field(p + 'wage', 'Wage', l.wage, { num: true, pre: '$' }) + field(p + 'burden_pct', 'Burden', l.burden_pct, { num: true, suf: '%' }) + '<button class="del" data-act="del" data-l="labor" data-i="' + i + '" aria-label="Remove">✕</button></div>';
      }).join('') + '<button class="btn ghost sm add" data-act="addlabor">+ Labor line</button>' +
      '<div class="hint" style="margin-top:14px">CM-owned equipment, to check the Blue Book rate</div>' + f.equipment.map(function (e, i) {
        var p = 'equipment.' + i + '.'; return '<div class="rowline eq">' + field(p + 'desc', 'Equipment', e.desc) + field(p + 'hours', 'Hours', e.hours, { num: true }) + field(p + 'rate', 'Rate charged', e.rate, { num: true, pre: '$' }) + field(p + 'blue_book', 'Blue Book rate', e.blue_book, { num: true, pre: '$' }) + '<button class="del" data-act="del" data-l="equipment" data-i="' + i + '" aria-label="Remove">✕</button></div>';
      }).join('') + '<button class="btn ghost sm add" data-act="addequip">+ Equipment line</button></div>';
    h += '<div class="card sec"><div class="sec-h"><h3>Other costs billed at cost</h3></div><div class="grid">' +
      field('nss', 'Site services', f.nss, { num: true, pre: '$', small: '(NSS) dumpsters, hoisting…' }) + field('sgc', 'General conditions items', f.sgc, { num: true, pre: '$', small: '(SGC)' }) +
      field('bond', 'Bond and insurance', f.bond, { num: true, pre: '$' }) + field('bo', 'B&O tax', f.bo, { num: true, pre: '$' }) +
      field('permits', 'Permit fees', f.permits, { num: true, pre: '$' }) + field('ext_sgc', 'Extended general conditions', f.ext_sgc, { num: true, pre: '$', small: '(time)' }) + '</div></div>';
    h += '<div class="card sec"><div class="sec-h"><h3>CM fee and totals</h3></div><div class="grid">' + field('fee_pct', 'CM fee', f.fee_pct, { num: true, suf: '%', small: '(the CM’s percentage)' }) + '<div></div></div>' +
      '<div class="hint" style="margin:12px 0 7px">The fee was charged on</div><div class="pills">' + K.FEE_ON.map(function (p) { return '<button class="pill" data-feeon="' + esc(p[0]) + '" aria-pressed="' + (f.fee_on.indexOf(p[0]) >= 0) + '">' + esc(FEE_LABEL[p[0]]) + '</button>'; }).join('') + '</div>' +
      '<div class="totals" style="margin-top:14px">' + field('fee_amount', 'CM fee amount', f.fee_amount, { num: true, pre: '$', small: f._fee_manual ? 'as written' : 'calculated' }) +
      field('total', 'Total requested', f.total, { num: true, pre: '$', small: f._total_manual ? 'as written on the cover sheet' : 'calculated' }) + '</div>' +
      '<div id="totnote"></div></div>';
    h += '<div class="stick"><div class="live" id="live"></div><button class="btn primary" data-act="check">' + (role === 'owner' || role === 'architect' ? 'Looks right, check it →' : 'Looks right, check it →') + '</button></div></div></div></div>';
    app.innerHTML = h;
    if (S.pdf && S.pdf.canvases) { var box = document.getElementById('pdfpages'); S.pdf.canvases.forEach(function (c) { box.appendChild(c); }); }
    live();
  }
  function live() {
    var f = S.form, el = document.getElementById('live'), tn = document.getElementById('totnote'); if (!el) return;
    if (S.edited) retotal(f); else f._lines_total = linesTotal(f);
    var ft = document.querySelector('[data-p="fee_amount"]'), tt = document.querySelector('[data-p="total"]');
    if (ft && document.activeElement !== ft) ft.value = fmt(f.fee_amount); if (tt && document.activeElement !== tt) tt.value = fmt(f.total);
    if (tn) tn.innerHTML = Math.abs(f._lines_total - f.total) > 1 ? '<p class="hint" style="color:var(--amber)">The cover sheet says ' + M(f.total) + ' but its lines add up to ' + M(f._lines_total) + '. <button class="link" data-act="usecalc">Use the lines’ total</button></p>' : '';
    if (!ready(f)) { el.innerHTML = '<span>Fill in what caused the change and both dates to check it.</span>'; return; }
    var cs = filtered(K.checksheet(caseOf(f), C())), n = cs.counts;
    el.innerHTML = '<span>Right now:</span>' + (n.fail ? '<b><span class="dotc" style="background:var(--red)"></span> ' + n.fail + ' problem' + (n.fail > 1 ? 's' : '') + '</b>' : '<b><span class="dotc" style="background:var(--green)"></span> no problems</b>') +
      (n.person ? '<span>· ' + n.person + ' for a person</span>' : '') + '<span>· ' + n.pass + ' checks pass</span>';
  }
  function setPath(o, path, v) { var ks = path.split('.'), last = ks.pop(); ks.forEach(function (k) { o = o[k]; }); o[last] = v; }
  app.addEventListener('input', function (e) {
    var t = e.target, p = t.dataset && t.dataset.p; if (!p || !S) return;
    var v = t.type === 'checkbox' ? t.checked : t.dataset.num ? num(t.value) : t.value;
    setPath(S.form, p, v); S.edited = true; S.need = S.need.filter(function (x) { return x !== p; }); t.closest('.inp') && t.closest('.inp').classList.remove('need');
    if (p === 'fee_amount') S.form._fee_manual = true; if (p === 'total') S.form._total_manual = true;
    if (t.type === 'checkbox' || t.tagName === 'SELECT') { saveSession(); return viewConfirmKeepScroll(); }
    live(); saveSession();
  });
  function viewConfirmKeepScroll() { var y = window.scrollY; viewConfirm(); window.scrollTo(0, y); }

  /* ---------- step 3: results ---------- */
  function filtered(cs) {
    if (role !== 'sub') return cs;
    var rows = cs.rows.filter(function (r) { return r.firm; }), counts = { pass: 0, fail: 0, person: 0, not_checked: 0 }, at = 0;
    rows.forEach(function (r) { counts[r.status]++; if (r.status === 'fail' && r.difference > 0) at += r.difference; });
    return Object.assign({}, cs, { rows: rows, counts: counts, dollars_at_issue: K.round(at, 2) });
  }
  function findingsOf(cs) {
    var order = { fail: 0, not_checked: 1, person: 2 };
    return cs.rows.filter(function (r) { return r.status !== 'pass'; })
      .sort(function (a, b) { return order[a.status] - order[b.status] || (b.difference || 0) - (a.difference || 0); })
      .map(function (r, i) { return { n: i + 1, r: r, kind: r.status === 'fail' ? 'fail' : r.status === 'person' ? 'person' : 'nc', p: K.plain(r, role, C()) }; });
  }
  function viewResult() {
    if (!S) return go('upload');
    if (!ready(S.form)) { go('confirm'); return toast('Fill in what caused the change and both dates first.'); }
    var f = S.form, cp = caseOf(f), full = K.checksheet(cp, C()), cs = filtered(full), fds = findingsOf(cs), v = K.verdict(cs, role), owner = role === 'owner' || role === 'architect';
    var fails = fds.filter(function (x) { return x.kind === 'fail'; }).length;
    var head = v.tone !== 'fail' ? '<em>' + esc(v.head) + '</em>'
      : owner ? '<em>' + fails + ' pricing ' + (fails === 1 ? 'problem' : 'problems') + '</em> to send back'
      : '<em>' + fails + (fails === 1 ? ' thing' : ' things') + '</em> will get this sent back';
    var noSub = role === 'sub' && !cp.subcontractor_quotes.length;
    var h = '<div class="wrap">' + steps(3) + '<div class="cols result"><div>' + paperHtml(cp, fds, 'Cover sheet, marked up').replace('<div class="paper">', '<div class="paper' + (S.lifted ? ' lifted' : '') + '">') +
      '<button class="btn sm lift" data-act="lift">' + (S.lifted ? 'Lay the markup back' : 'Lift the markup') + '</button><p class="paper-cap">' + (S.source === 'pdf' ? 'Rebuilt from the numbers you confirmed, not the original file.' : S.source === 'sample' ? 'Synthetic sample proposal.' : 'Built from the numbers you entered.') + '</p></div>' +
      '<div class="card findings"><div class="verdict ' + v.tone + '"><span class="eyebrow">' + esc(K.ROLE[role].label) + ' view · ' + esc(cp.id) + '</span>';
    if (noSub) h += '<h2>No subcontractor quote here</h2><p>Switch to GC/CM or Owner’s rep to see the whole proposal.</p></div>';
    else h += '<h2>' + head + '</h2><p>' + esc(v.sub) + '</p><div class="vrow">' + (cs.dollars_at_issue > 0 ? '<div class="atissue"><b>' + M(cs.dollars_at_issue) + '</b><span>' + (owner ? 'more than the contract allows' : 'over what the contract allows') + '</span></div>' : '<div></div>') + stamp(cs, fails) + '</div></div>';
    if (!noSub) {
      h += fds.length ? '<ol class="fl">' + fds.map(function (fd) {
        return '<li class="' + fd.kind + '" data-n="' + fd.n + '"><span class="n">' + tag(fd.n, fd.kind) + '</span><div><b>' + esc(fd.p.title) + '</b><p>' + esc(fd.p.why) + '</p>' + (fd.p.amt ? '<p class="money">' + M(fd.p.amt) + ' ' + (owner ? 'more than allowed' : 'too much') + '</p>' : '') +
          '<div style="margin-top:6px"><span class="zref" data-zn="' + fd.n + '" hidden></span></div><details class="why"><summary>What the contract says</summary><div class="box"><span>Contract</span><span>' + esc(fd.r.contract) + '</span><span>Proposal</span><span>' + esc(fd.r.proposal) + '</span><span>Clause</span><span>§ ' + esc(fd.r.section) + '</span></div></details></div></li>';
      }).join('') + '</ol>' : '<ol class="fl"></ol>';
      var passed = cs.rows.filter(function (r) { return r.status === 'pass'; });
      h += '<details class="passed"><summary><span>✓ ' + passed.length + ' ' + (fds.length ? 'other ' : '') + 'checks passed</span><span>show ▾</span></summary><ul>' + passed.map(function (r) { return '<li><span>' + esc(r.check) + '</span><code>§ ' + esc(r.section) + '</code></li>'; }).join('') + '</ul></details>';
      h += '<div class="notchecked">Not checked: whether the work is really a change, whether costs are already covered by the fee, and whether hours and prices are reasonable. ' + (owner ? 'Those are yours to judge.' : 'The owner’s rep will still judge those.') + '</div>';
    }
    var acts = owner ? '<button class="btn primary" data-act="copy">Copy notes to send back</button><button class="btn" data-act="edit">Edit the numbers</button><button class="btn ghost" data-act="new">Check another</button>'
      : '<button class="btn primary" data-act="edit">' + (fails ? 'Fix and re-check' : 'Edit the numbers') + '</button><button class="btn" data-act="copy">Copy summary</button><button class="btn ghost" data-act="new">Check another</button>';
    if (cp.time_impact_days > 0) acts += '<button class="btn" data-act="todelay">Check the ' + cp.time_impact_days + ' days against the schedule</button>';
    h += '<div class="acts">' + acts + '</div>' + '' + '</div></div></div>';
    app.innerHTML = h;
    requestAnimationFrame(function () { frame(); drawClouds(true); }); if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { frame(); drawClouds(false); });
  }
  // The verdict as a submittal review stamp, the way a reviewer returns a submittal.
  function stamp(cs, fails) {
    var n = cs.counts, pick = fails ? 'Revise and resubmit' : 'No exceptions taken';
    var opts = ['No exceptions taken', 'Make corrections noted', 'Revise and resubmit', 'Rejected'];
    return '<div class="stamp land' + (fails ? '' : ' ink') + '" role="img" aria-label="Review stamp: ' + pick + '"><div class="st-h">Checked by ClauseStream</div>' +
      opts.map(function (o) { return '<div' + (o === pick ? ' class="on"' : '') + '>' + (o === pick ? '☒ ' : '☐ ') + o + '</div>'; }).join('') +
      '<div class="st-f">' + (n.person ? n.person + ' for the owner’s rep to decide' : 'Against ' + esc(C().name)) + '</div></div>';
  }
  function notesText() {
    var f = S.form, cp = caseOf(f), cs = filtered(K.checksheet(cp, C())), fds = findingsOf(cs), owner = role === 'owner' || role === 'architect';
    var t = cp.id + ' · ' + cp.title + ' · ' + M(cp.cover_sheet.total_requested) + '\nChecked against: ' + C().name + '.\n\n';
    if (!fds.length) t += 'Every computed check passes.\n';
    fds.forEach(function (fd) { t += fd.n + '. ' + fd.p.title + ' ' + fd.p.why + (fd.p.amt ? ' ' + M(fd.p.amt) + (owner ? ' more than allowed.' : ' too much.') : '') + ' (§ ' + fd.r.section + ')\n'; });
    if (cs.dollars_at_issue > 0) t += '\nTotal at issue: ' + M(cs.dollars_at_issue) + '\n';
    return t;
  }

  /* ---------- contracts: load your own, confirm every term, then the checks use it ---------- */
  var CT = window.ClauseContract, CS = null, _C = null;
  var GROUPS = [['Pricing', 'Pricing limits'], ['Notice', 'Notice deadlines'], ['Time', 'Time and delay']];
  function contracts() { return store('cs_contracts') || []; }
  function activeId() { return store('cs_active') || 'sample'; }
  function C() {
    if (_C) return _C;
    var x = contracts().filter(function (c) { return c.id === activeId(); })[0];
    _C = x ? K.fromTerms(x.name, CT.toTerms(x.read)) : K.CONTRACT; return _C;
  }
  function setActive(id) { store('cs_active', id); _C = null; chip(); }
  function chip() { var b = document.querySelector('#contractBtn b'); if (b) b.textContent = C().name; }
  function pctTxt(v) { return v == null ? '—' : v + '%'; }
  function feeOnTxt(a) { return (a || []).map(function (p) { var l = FEE_LABEL[p] || p; return /^[A-Z]{2}/.test(l) ? l : l.charAt(0).toLowerCase() + l.slice(1); }).join(' and ') || 'nothing'; }
  function partiesTxt(a) { return (a || []).map(function (p) { return p === 'owner' ? 'the owner' : p === 'architect' ? 'the architect' : p; }).join(' or ') || 'no one'; }
  function concTxt(v) { var x = CT.CONCURRENT.filter(function (c) { return c[0] === v; })[0]; return x ? x[1] : '—'; }
  function renderModal() {
    var c = C(), s = c.sections, nb = c.noticeByCause, list = contracts(), act = activeId();
    var def = c.defaulted && c.defaulted.length ? '<p class="fine" style="color:var(--amber)">Not set for this contract, so the sample’s value is used: ' + c.defaulted.map(function (k) { var t = CT.TERMS.filter(function (x) { return x[0] === k || (k === 'notice_days_by_cause' && x[0] === 'notice_days_standard'); })[0]; return t ? t[1].split(':')[0] : k; }).join(', ') + '.</p>' : '';
    var rules = [
      ['Subcontractor markup', 'Up to ' + pctTxt(c.markupOwn) + ' on their own work, ' + pctTxt(c.markupLower) + ' on lower-tier subs, ' + pctTxt(c.markupTotal) + ' in total.', s.markup],
      ['CM fee', pctTxt(c.feePercent) + ', and only on ' + feeOnTxt(c.feeAllowedOn) + '.', s.fee],
      ['Labor burden', pctTxt(c.burdenPercent) + ' on top of wages.', s.burden],
      ['CM-owned equipment', 'At most ' + pctTxt(c.blueBookPercent) + ' of the Rental Rate Blue Book rate.', s.equipment],
      ['Notice', 'Within ' + nb['RFI response'] + ' days of an RFI answer, ASI, returned submittal, direction or hidden site condition; ' + nb['Other event'] + ' days for anything else. A deadline on a weekend or holiday moves to the next business day.', (c.noticeSection && c.noticeSection['RFI response']) || '6.2'],
      ['Goes to a person', 'Time extensions, hidden site conditions, and anything over ' + M(c.approvalLimit) + '.', s.approval],
      ['Time', c.contractDays + ' days to substantial completion; ' + M(c.ldPerDay) + '/day liquidated damages; extended general conditions at ' + M(c.dailyDelayRate) + '/day.', ''],
      ['Delay', (c.extensionRequiresCriticalPath ? 'Extensions only for delays on the critical path. ' : '') + 'Delays caused by ' + partiesTxt(c.compensableCauses) + ' are paid. Concurrent delay: ' + concTxt(c.concurrentDelay).toLowerCase() + '.', '']
    ];
    document.getElementById('cmTitle').textContent = c.name;
    document.getElementById('cmBody').innerHTML = '<ul class="rules">' + rules.map(function (r) { return '<li><b>' + r[0] + '</b><span>' + esc(r[1]) + '</span>' + (r[2] ? '<code>§ ' + esc(r[2]) + '</code>' : '<code></code>') + '</li>'; }).join('') + '</ul>' + def +
      '<div class="clist"><div class="clist-h"><span class="eyebrow">Your contracts</span><a class="btn sm primary" href="#contract" data-close>+ Load a contract</a></div>' +
      [{ id: 'sample', name: K.CONTRACT.name, sub: 'Synthetic, written for this project' }].concat(list.map(function (x) { return { id: x.id, name: x.name, sub: (x.file || 'Entered by hand') + ' · confirmed ' + new Date(x.saved).toLocaleDateString(), own: true }; })).map(function (x) {
        return '<div class="crow' + (x.id === act ? ' on' : '') + '"><button class="cpick" data-cpick="' + esc(x.id) + '"><span class="radio"></span><span><b>' + esc(x.name) + '</b><small>' + esc(x.sub) + '</small></span></button>' +
          (x.own ? '<button class="btn ghost sm" data-cedit="' + esc(x.id) + '">Edit terms</button><button class="btn ghost sm" data-cdel="' + esc(x.id) + '" aria-label="Remove">✕</button>' : '') + '</div>';
      }).join('') + '</div>' +
      '<p class="fine">Contracts you load are kept in this browser only. The sample is a synthetic contract modeled on the Webster School audit.</p>';
  }

  function viewContract(err) {
    app.innerHTML = '<div class="wrap"><section class="upload"><span class="eyebrow">Load a contract</span><h1 style="margin-top:10px">Check proposals against your own contract</h1>' +
      '<p class="lede">We find the clauses that set markups, the fee, notice deadlines and delay terms. You confirm each one, with the sentence it came from, before any check uses it.</p>' +
      '<div class="drop" id="drop"><div class="ic"></div><b>Drop the contract here</b><p>PDF with a text layer, or .txt / .md.</p>' +
      '<label class="btn primary">Choose a file<input type="file" accept=".pdf,.txt,.md,application/pdf,text/plain" id="file" hidden></label>' +
      '<span class="or">or try a sample: <button class="link" data-act="csample" data-c="A">contract A</button> · <button class="link" data-act="csample" data-c="B">contract B (different terms)</button></span>' +
      '<div class="reader ' + (reader ? 'on' : '') + '"><span class="dot"></span>' + (reader ? 'Clause reading is on: ' + esc(reader) + ' running on this computer' : 'Here, keyword search finds the candidate sentences and you pick. The AI reader runs on the team’s laptop.') + '</div></div>' +
      (store('cs_reader_target') ? '<div class="banner"><span>Reading the terms of <b>' + esc(store('cs_reader_target').title) + '</b>. They’ll be saved to that contract on your project. <button class="link" data-act="cuntarget">Not this contract</button></span></div>' : '') +
      (err ? '<div class="err">' + esc(err) + '</div>' : '') +
      '<ol class="how"><li><b>Code</b> splits the contract into numbered sentences and keeps each one’s section.</li><li><b>Code</b> finds the few sentences that could state each term.</li>' +
      '<li><b>The AI</b> may only pick one of those sentences, or say “not stated”. It reads three times; if the readings differ, the term is flagged.</li><li><b>Code</b> checks the number is really in the sentence.</li><li><b>You</b> confirm every term. Terms not found use the sample’s value, and we say so.</li></ol></section></div>';
    var drop = document.getElementById('drop');
    ['dragenter', 'dragover'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('over'); }); });
    ['dragleave', 'drop'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('over'); }); });
    drop.addEventListener('drop', function (e) { var f = e.dataTransfer.files[0]; if (f) contractFile(f); });
    document.getElementById('file').addEventListener('change', function (e) { if (e.target.files[0]) contractFile(e.target.files[0]); });
  }
  function pdfText(file) {
    return loadPdfjs().then(function (lib) { return file.arrayBuffer().then(function (buf) { return lib.getDocument({ data: buf }).promise; }); }).then(function (doc) {
      var jobs = []; for (var i = 1; i <= doc.numPages; i++) jobs.push(doc.getPage(i).then(function (pg) { return pg.getTextContent().then(function (tc) { return { n: pg.pageNumber, t: tc.items.map(function (it) { return it.str + (it.hasEOL ? '\n' : ' '); }).join('') }; }); }));
      return Promise.all(jobs).then(function (r) { return r.sort(function (a, b) { return a.n - b.n; }).map(function (x) { return x.t; }).join('\n'); });
    });
  }
  function contractFile(file) {
    var isPdf = /\.pdf$/i.test(file.name) || file.type === 'application/pdf';
    if (!isPdf && !/\.(txt|md|markdown)$/i.test(file.name)) return viewContract('Use a PDF, .txt or .md file. For a Word file, save it as PDF first.');
    app.innerHTML = '<div class="wrap"><div class="reading"><div class="spinner"></div><h2>Opening ' + esc(file.name) + '…</h2></div></div>';
    (isPdf ? pdfText(file) : file.text()).then(function (text) {
      if (text.replace(/\s/g, '').length < 200) return viewContract('No readable text in ' + file.name + '. A scanned PDF has no text layer.');
      readContract(text, file.name.replace(/\.[^.]+$/, ''), file.name);
    }).catch(function (e) { viewContract('Could not open that file: ' + e.message); });
  }
  function newCS(text, name, file) {
    var r = CT.retrieve(text), by = {}; r.sentences.forEach(function (s) { by[s.id] = s; });
    return { id: 'k' + Date.now().toString(36), name: name, file: file, text: text, sents: r.sentences, by: by, cands: r.candidates, read: {}, source: 'search' };
  }
  function applyReading(cs, j) {
    Object.keys(j.read).forEach(function (k) {
      var x = j.read[k], s = cs.sents.filter(function (y) { return y.text === x.quote; })[0];
      cs.read[k] = { value: x.value, quote: x.quote, section: x.section, sid: s ? s.id : null, status: x.status === 'not_stated' ? 'none' : x.status, src: 'ai', note: x.note };
    });
  }
  function readContract(text, name, file, savedRun) {
    var cs = newCS(text, name, file);
    CT.TERMS.forEach(function (t) { cs.read[t[0]] = { value: null, quote: null, section: null, sid: null, status: 'pick', src: null, note: '' }; });
    if (!reader && savedRun) { applyReading(cs, savedRun.run); cs.source = 'ai'; cs.model = savedRun.meta.model + ' (saved run)'; cs.secs = savedRun.run.seconds; CS = cs; return go('contract-confirm'); }
    if (!reader) { CS = cs; return go('contract-confirm'); }
    var t0 = Date.now(), cancelled = false;
    app.innerHTML = '<div class="wrap"><div class="reading"><div class="spinner"></div><h2>Reading ' + esc(file || name) + '</h2><p class="fine" style="font-size:13.5px">' + esc(reader) +
      ' is picking the clause for each of ' + CT.TERMS.length + ' terms, three times over. A few minutes. <span id="tick">0:00</span></p><p style="margin-top:18px"><button class="btn ghost sm" id="cancel">Pick the clauses myself instead</button></p></div></div>';
    var tick = setInterval(function () { var s = Math.round((Date.now() - t0) / 1000), el = document.getElementById('tick'); if (el) el.textContent = Math.floor(s / 60) + ':' + ('0' + s % 60).slice(-2); }, 1000);
    document.getElementById('cancel').onclick = function () { cancelled = true; clearInterval(tick); CS = cs; go('contract-confirm'); };
    fetch('/api/contract', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: text, runs: 3 }) })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || 'HTTP ' + r.status); return j; }); })
      .then(function (j) {
        if (cancelled) return; clearInterval(tick);
        applyReading(cs, j);
        cs.source = 'ai'; cs.model = j.model; cs.secs = j.seconds; CS = cs; go('contract-confirm');
      })
      .catch(function (e) { if (cancelled) return; clearInterval(tick); cs.banner = 'The local model couldn’t read it (' + e.message + '). Pick the clauses below instead.'; CS = cs; go('contract-confirm'); });
  }
  // A value copied from a chosen sentence (no model): the number next to %, $ or "days". The person checks it.
  // When a sentence has several numbers, take the one nearest a word specific to the term ("lower-tier", "total", "own").
  var NEAR = { markup_own_pct: ['own'], markup_lower_pct: ['lower'], markup_total_pct: ['total', 'combined', 'in no event', 'aggregate'], notice_days_other: ['other'],
    notice_days_standard: ['rfi', 'direction', 'concealed', 'asi'], daily_delay_rate: ['daily', 'per day'], sgc_total: ['sgc is', 'general conditions'], liquidated_damages_per_day: ['each day', 'per day'] };
  function guess(kind, s, k) {
    var t = s.text, l = t.toLowerCase(), re = kind === 'pct' ? /(\d+(?:\.\d+)?)\s*%/g : kind === 'money' ? /\$\s?([\d,]+(?:\.\d+)?)/g : kind === 'days' ? /(\d+)\s*(?:\(\d+\)\s*)?(?:calendar |working |business )?days?\b/gi : null, m;
    if (re) {
      var hits = []; while ((m = re.exec(t))) hits.push({ v: +m[1].replace(/,/g, ''), at: m.index });
      if (!hits.length && kind === 'days' && (m = t.match(/\((\d+)\)/))) return +m[1];
      if (!hits.length) return null;
      var words = NEAR[k] || [], pos = []; words.forEach(function (w) { var i = -1; while ((i = l.indexOf(w, i + 1)) >= 0) pos.push(i); });
      if (!pos.length) return hits[0].v;
      hits.sort(function (a, b) { return Math.min.apply(null, pos.map(function (p) { return Math.abs(a.at - p); })) - Math.min.apply(null, pos.map(function (p) { return Math.abs(b.at - p); })); });
      return hits[0].v;
    }
    var l = t.toLowerCase();
    if (kind === 'bool') return l.indexOf('critical path') >= 0;
    if (kind === 'parties') return ['owner', 'architect'].filter(function (p) { return l.indexOf(p) >= 0; });
    if (kind === 'concurrent') return /time but no|no compensation|without compensation/.test(l) ? 'time_no_money' : /neither|no time/.test(l) ? 'no_time_no_money' : /apportion/.test(l) ? 'apportioned' : 'not_stated';
    if (kind === 'fee_on') return CT.FEE_ON.filter(function (p) { return (p === 'CM direct costs' ? ['direct cost', 'cost of the work'] : p === 'subcontractor quotes' ? ['subcontract'] : []).some(function (w) { return l.indexOf(w) >= 0; }); });
    return null;
  }
  function kindOfTerm(k) { return CT.TERMS.filter(function (t) { return t[0] === k; })[0][2]; }
  function restatus(k) {
    var x = CS.read[k], kind = kindOfTerm(k);
    if (!x.sid) { x.status = x.value == null || x.value === '' ? 'none' : 'manual'; x.note = x.status === 'manual' ? 'entered without a source sentence' : 'not stated'; return; }
    var sn = CS.by[x.sid], v = CT.verify(k, kind, x.value, sn, CT.contextFor(sn, CS.sents, CS.heads || (CS.heads = CT.headings(CS.text)))); x.status = v[0] ? 'verified' : 'check'; x.note = v[1];
  }
  function pickSentence(k, sid) {
    var x = CS.read[k], s = sid ? CS.by[sid] : null;
    x.sid = sid || null; x.quote = s ? s.text : null; x.section = s ? s.section : null;
    if (s && x.src !== 'person') { x.value = guess(kindOfTerm(k), s, k); x.src = 'search'; }
    if (!s && x.src !== 'person') x.value = null;
    restatus(k);
  }
  function termInput(k, kind, v) {
    if (kind === 'fee_on') return '<div class="pills">' + CT.FEE_ON.map(function (p) { return '<button class="pill" data-tpill="' + k + '|' + esc(p) + '" aria-pressed="' + ((v || []).indexOf(p) >= 0) + '">' + esc(FEE_LABEL[p]) + '</button>'; }).join('') + '</div>';
    if (kind === 'parties') return '<div class="pills">' + ['owner', 'architect', 'contractor'].map(function (p) { return '<button class="pill" data-tpill="' + k + '|' + p + '" aria-pressed="' + ((v || []).indexOf(p) >= 0) + '">' + p.charAt(0).toUpperCase() + p.slice(1) + '</button>'; }).join('') + '</div>';
    if (kind === 'concurrent') return '<div class="inp sel"><select data-t="' + k + '"><option value="">Choose…</option>' + CT.CONCURRENT.map(function (c) { return '<option value="' + c[0] + '"' + (c[0] === v ? ' selected' : '') + '>' + c[1] + '</option>'; }).join('') + '</select></div>';
    if (kind === 'bool') return '<div class="inp sel"><select data-t="' + k + '"><option value="">Choose…</option><option value="true"' + (v === true ? ' selected' : '') + '>Yes</option><option value="false"' + (v === false ? ' selected' : '') + '>No</option></select></div>';
    return '<div class="inp">' + (kind === 'money' ? '<span class="pre">$</span>' : '') + '<input data-t="' + k + '" inputmode="decimal" value="' + esc(v == null ? '' : v) + '">' + (kind === 'pct' ? '<span class="suf">%</span>' : kind === 'days' ? '<span class="suf">days</span>' : '') + '</div>';
  }
  var SAMPLE_VALUE = null;
  function sampleVal(k) { SAMPLE_VALUE = SAMPLE_VALUE || CT.sampleReading(K.CONTRACT); var v = SAMPLE_VALUE[k].value; return Array.isArray(v) ? v.join(', ') : typeof v === 'boolean' ? (v ? 'yes' : 'no') : v; }
  var TAG = { verified: '<span class="tagr ok">in the quote</span>', check: '<span class="tagr chk">check this</span>', none: '<span class="tagr none">not found</span>', pick: '<span class="tagr none">pick a sentence</span>', manual: '<span class="tagr chk">no source</span>' };
  var SRC = { ai: 'AI pick', search: 'copied from the sentence you picked', person: 'you edited' };
  function termHtml(t) {
    var k = t[0], kind = t[2], x = CS.read[k], cands = CS.cands[k];
    var quote = x.sid ? '<button class="quote" data-jump="' + x.sid + '"><span>“' + esc(x.quote) + '”</span><code>§ ' + esc(x.section || '—') + '</code></button>'
      : '<div class="quote none">' + (x.status === 'pick' ? (cands.length ? 'Pick the sentence that states this:' : 'No sentence in this contract mentions it.') : 'Not stated in this contract.') + ' Left blank, the sample’s value (' + esc(sampleVal(k)) + ') is used.</div>';
    var opts = cands.length ? '<details class="alts"' + (x.status === 'pick' || x.status === 'check' ? ' open' : '') + '><summary>' + (x.sid ? 'Other sentences' : 'Candidate sentences') + ' (' + cands.length + ')</summary>' +
      cands.map(function (s) { return '<button class="alt' + (s.id === x.sid ? ' on' : '') + '" data-pick="' + k + '|' + s.id + '"><code>§ ' + esc(s.section || '—') + '</code><span>' + esc(s.text) + '</span></button>'; }).join('') +
      '<button class="alt" data-pick="' + k + '|"><code>—</code><span>None of these states it</span></button></details>' : '';
    return '<div class="term s-' + x.status + '" id="t-' + k + '"><div class="term-h"><b>' + esc(t[1]) + '</b>' + TAG[x.status] + '</div>' + termInput(k, kind, x.value) +
      (x.src ? '<div class="src">' + esc(SRC[x.src] || '') + (x.note && x.status !== 'verified' ? ' · ' + esc(x.note) : '') + '</div>' : '') + quote + opts + '</div>';
  }
  function viewContractConfirm() {
    if (!CS) return go('contract');
    var used = {}; Object.keys(CS.read).forEach(function (k) { if (CS.read[k].sid) used[CS.read[k].sid] = 1; });
    var cnt = { verified: 0, check: 0, none: 0, pick: 0, manual: 0 }; Object.keys(CS.read).forEach(function (k) { cnt[CS.read[k].status]++; });
    var left = '<div class="paper ctext"><div class="ph"><span class="eyebrow">' + esc(CS.file || 'Contract') + '</span><span class="eyebrow">' + CS.sents.length + ' sentences</span></div><div class="ctext-body">' +
      CS.sents.map(function (s, i) { var head = i === 0 || s.section !== CS.sents[i - 1].section; return (head ? '<div class="csec">§ ' + esc(s.section || '—') + '</div>' : '') + '<span id="s-' + s.id + '"' + (used[s.id] ? ' class="used"' : '') + '>' + esc(s.text) + ' </span>'; }).join('') + '</div></div>';
    var banner = CS.banner ? '<div class="banner warn">' + esc(CS.banner) + '</div>'
      : CS.source === 'ai' ? '<div class="banner"><span><b>' + esc(CS.model) + '</b> picked a sentence for each term' + (CS.secs ? ' in ' + Math.round(CS.secs) + ' s' : '') + '. <span class="tagr ok">in the quote</span> means code found the value in that sentence and all three readings agreed. Everything else needs your eye.</span></div>'
      : CS.source === 'edit' ? '' : '<div class="banner"><span>Keyword search found the candidate sentences. Pick the one that states each term; we copy the number from it and you check it.</span></div>';
    var h = '<div class="wrap"><div class="cols"><div>' + left + '</div><div class="form"><h2>Confirm the contract terms</h2><p class="sub">Every check uses these numbers. Click a quote to see it in the contract.</p>' + banner +
      '<div class="card sec"><div class="grid"><div class="fd full"><label><span>Contract name</span></label><div class="inp"><input id="cname" value="' + esc(CS.name) + '"></div></div></div>' +
      '<div class="ccount"><span class="tagr ok">' + cnt.verified + ' in the quote</span><span class="tagr chk">' + (cnt.check + cnt.manual) + ' to check</span><span class="tagr none">' + (cnt.none + cnt.pick) + ' not set</span></div></div>' +
      GROUPS.map(function (g) { return '<div class="card sec"><div class="sec-h"><h3>' + g[1] + '</h3></div>' + CT.TERMS.filter(function (t) { return t[4] === g[0]; }).map(termHtml).join('') + '</div>'; }).join('') +
      '<div class="stick"><div class="live"><span>' + (cnt.none + cnt.pick ? (cnt.none + cnt.pick) + ' not set' : 'All terms set') + '</span></div><button class="btn ghost" data-go="contract">Cancel</button><button class="btn primary" data-act="csave">Use this contract →</button></div></div></div></div>';
    app.innerHTML = h;
  }
  function contractKeepScroll() { var y = window.scrollY; viewContractConfirm(); window.scrollTo(0, y); }
  function saveContract() {
    var name = (document.getElementById('cname').value || '').trim() || 'My contract', read = {};
    Object.keys(CS.read).forEach(function (k) { var x = CS.read[k], ok = x.value != null && x.value !== '' && !(Array.isArray(x.value) && !x.value.length && kindOfTerm(k) !== 'parties');
      read[k] = { value: ok ? x.value : null, quote: x.quote, section: x.section, status: ok ? x.status : 'none', src: x.src, note: x.note }; });
    // Reading the terms of a contract on a project: save them to that contract, then go back to 03 Contracts.
    var tgt = store('cs_reader_target'), PL = window.CSPlat;
    if (tgt && PL && PL.ctx() && PL.ctx().project.id === tgt.project) return saveToProject(tgt, read, PL);
    var rec = { id: CS.id, name: name, file: CS.file, saved: Date.now(), source: CS.source, model: CS.model || null, read: read, text: CS.text.length < 400000 ? CS.text : null };
    var list = contracts().filter(function (c) { return c.id !== rec.id; }); list.unshift(rec); store('cs_contracts', list.slice(0, 10));
    setActive(rec.id); CS = null; toast('Checks now use “' + name + '”.'); go(S ? 'result' : 'upload');
  }
  function saveToProject(tgt, read, PL) {
    var sb = PL.sb(), now = new Date().toISOString(), uid = PL.user() && PL.user().id;
    // A term marked "to check" in the reader is saved unconfirmed, so it waits for a Confirm on 03 Contracts.
    var rows = Object.keys(read).filter(function (k) { return read[k].value != null; }).map(function (k) {
      var x = read[k], ok = x.status !== 'check';
      return { project_id: tgt.project, contract_id: tgt.contract, key: k, value: x.value, clause: x.section ? '§ ' + x.section : null, sentence: x.quote || null, confirmed_by: ok ? uid : null, confirmed_at: ok ? now : null };
    });
    PL.q(sb.from('contract_terms').select('id,key').eq('contract_id', tgt.contract)).then(function (have) {
      var byKey = {}; have.forEach(function (h) { byKey[h.key] = h.id; });
      return Promise.all(rows.map(function (r) { return byKey[r.key] ? PL.q(sb.from('contract_terms').update(r).eq('id', byKey[r.key])) : PL.q(sb.from('contract_terms').insert(r)); }));
    }).then(function () { return PL.loadCtx(tgt.project); }).then(function () {
      store('cs_reader_target', null); CS = null; toast(rows.length + ' terms saved to ' + tgt.title + '.'); go('contracts');
    }).catch(function (e) { toast('Could not save the terms: ' + (e.message || e)); });
  }
  function editContract(id) {
    var x = contracts().filter(function (c) { return c.id === id; })[0]; if (!x) return;
    if (!x.text) return toast('The text of this contract wasn’t kept, so it can’t be re-opened.');
    var cs = newCS(x.text, x.name, x.file); cs.id = x.id; cs.source = 'edit';
    Object.keys(x.read).forEach(function (k) { var r = x.read[k], s = cs.sents.filter(function (y) { return y.text === r.quote; })[0]; cs.read[k] = { value: r.value, quote: r.quote, section: r.section, sid: s ? s.id : null, status: r.status, src: r.src, note: r.note }; });
    CS = cs; go('contract-confirm');
  }
  function onContractClick(t) {
    if (t.dataset.pick != null) { var p = t.dataset.pick.split('|'); pickSentence(p[0], p[1]); contractKeepScroll(); return true; }
    if (t.dataset.tpill) { var q = t.dataset.tpill.split('|'), x = CS.read[q[0]], a = Array.isArray(x.value) ? x.value.slice() : [], i = a.indexOf(q[1]); if (i >= 0) a.splice(i, 1); else a.push(q[1]); x.value = a; x.src = 'person'; restatus(q[0]); contractKeepScroll(); return true; }
    if (t.dataset.jump) { var el = document.getElementById('s-' + t.dataset.jump); if (el) { el.scrollIntoView({ block: 'center', behavior: 'smooth' }); el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash'); } return true; }
    if (t.dataset.act === 'csave') { saveContract(); return true; }
    if (t.dataset.act === 'csample') {
      var which = t.dataset.c || 'A', url = which === 'B' ? '/demo4/data/contract_b.md' : '/demo1/data/synthetic_contract.md';
      Promise.all([fetch(url).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); }),
        fetch('/demo4/results/contract_test.json').then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })])
        .then(function (res) { readContract(res[0], which === 'B' ? 'Contract B (synthetic)' : 'Contract A (sample, re-read)', which === 'B' ? 'contract_b.md' : 'synthetic_contract.md', res[1] && res[1].readings && res[1].readings[which] ? { run: res[1].readings[which], meta: res[1].meta } : null); })
        .catch(function (e) { viewContract('Could not load the sample text: ' + e.message); });
      return true;
    }
    return false;
  }
  app.addEventListener('change', function (e) {
    var k = e.target.dataset && e.target.dataset.t; if (!k || !CS) return;
    var kind = kindOfTerm(k), v = e.target.value, x = CS.read[k];
    x.value = kind === 'bool' ? (v === '' ? null : v === 'true') : kind === 'concurrent' ? (v || null) : (v.trim() === '' ? null : num(v));
    x.src = 'person'; restatus(k); contractKeepScroll();
  });

  /* ---------- events ---------- */
  app.addEventListener('click', function (e) {
    var t = e.target.closest('[data-act],[data-sample],[data-go],[data-feeon],[data-pick],[data-tpill],[data-jump]'); if (!t) return;
    if (t.dataset.act === 'cuntarget') { store('cs_reader_target', null); return viewContract(); }
    if (CS && onContractClick(t)) return; if (t.dataset.act === 'csample') return onContractClick(t);
    if (t.dataset.go) return go(t.dataset.go);
    if (t.dataset.feeon) { var on = S.form.fee_on, p = t.dataset.feeon, i = on.indexOf(p); if (i >= 0) on.splice(i, 1); else on.push(p); S.edited = true; t.setAttribute('aria-pressed', i < 0); live(); saveSession(); return; }
    if (t.dataset.sample) { startSample(t.dataset.sample); return go(t.closest('table') ? 'result' : 'confirm'); }
    var a = t.dataset.act, f = S && S.form;
    if (a === 'manual') { start(blankForm(), 'manual'); return go('confirm'); }
    if (a === 'addsub') { f.subs.push(blankSub()); S.edited = true; return viewConfirmKeepScroll(); }
    if (a === 'delsub') { f.subs.splice(+t.dataset.i, 1); S.edited = true; return viewConfirmKeepScroll(); }
    if (a === 'addtag') { var s = f.subs[+t.dataset.i]; s.tm_tags.push({ tag: 'TM-' + (s.tm_tags.length + 1), date: '', signed: false }); S.edited = true; return viewConfirmKeepScroll(); }
    if (a === 'addlabor') { f.labor.push({ desc: '', hours: 0, wage: 0, burden_pct: 32 }); S.edited = true; return viewConfirmKeepScroll(); }
    if (a === 'addequip') { f.equipment.push({ desc: '', hours: 0, rate: 0, blue_book: 0 }); S.edited = true; return viewConfirmKeepScroll(); }
    if (a === 'del') { f[t.dataset.l].splice(+t.dataset.i, 1); S.edited = true; return viewConfirmKeepScroll(); }
    if (a === 'usecalc') { f._total_manual = false; f._fee_manual = false; S.edited = true; return viewConfirmKeepScroll(); }
    if (a === 'check') {
      if (!ready(f)) { ['cause', 'event_date', 'notice_date'].forEach(function (k) { if (!f[k] || (k !== 'cause' && !/^\d{4}-/.test(f[k]))) S.need.indexOf(k) < 0 && S.need.push(k); }); viewConfirmKeepScroll(); return toast('Fill in what caused the change and both dates first.'); }
      saveSession(); return go('result');
    }
    if (a === 'todelay') { var cq = caseOf(S.form); store('cs_delay_prefill', { id: cq.id, title: cq.title, claimed_days: cq.time_impact_days, narrative: cq.narrative || '' }); return go('delay'); }
    if (a === 'lift') { S.lifted = !S.lifted; var pp = app.querySelector('.cols.result .paper'); if (pp) pp.classList.toggle('lifted', S.lifted); t.textContent = S.lifted ? 'Lay the markup back' : 'Lift the markup'; return; }
    if (a === 'edit') return go('confirm');
    if (a === 'new') { S = null; try { sessionStorage.removeItem('cs_current'); } catch (er) {} return go('upload'); }
    if (a === 'copy') { var txt = notesText(); (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(function () { toast('Copied. Paste it into your email or Procore.'); }, function () { window.prompt('Copy this:', txt); }); return; }
  });
  var modal = document.getElementById('contractModal');
  document.getElementById('contractBtn').onclick = function () { renderModal(); modal.hidden = false; };
  modal.addEventListener('click', function (e) {
    var t = e.target.closest('[data-cpick],[data-cedit],[data-cdel]');
    if (t && t.dataset.cpick) { setActive(t.dataset.cpick); renderModal(); toast('Checks now use “' + C().name + '”.'); if (/result|confirm/.test(location.hash)) route(); return; }
    if (t && t.dataset.cedit) { modal.hidden = true; return editContract(t.dataset.cedit); }
    if (t && t.dataset.cdel) { store('cs_contracts', contracts().filter(function (c) { return c.id !== t.dataset.cdel; })); if (activeId() === t.dataset.cdel) setActive('sample'); renderModal(); route(); return; }
    if (e.target === modal || e.target.closest('[data-close]')) modal.hidden = true;
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') modal.hidden = true; });

  // Shared with the schedule and delay views (assets/views-time.js).
  window.CSApp = { app: app, esc: esc, store: store, toast: toast, num: num, go: function (v) { go(v); }, loadPdfjs: loadPdfjs, pdfText: function (f) { return pdfText(f); },
    C: function () { return C(); }, tag: tag, frame: function () { frame(); }, reader: function () { return reader; }, M: M };

  /* ---------- routing ---------- */
  function go(v) { if (location.hash !== '#' + v) location.hash = v; else route(); }
  function route() {
    var full = (location.hash || '#home').slice(1), v = full.split('?')[0] || 'home';
    if (v === 'proposals') return go('changes');
    // A first visit to the app with no mode chosen opens the getting-started screen.
    if (v === 'home' && !store('cs_seen_start') && !store('cs_mode') && !store('cs_project') && !/[?&](signin|project|mode|sample)=/.test(location.search)) return go('start');
    var navKey = /^(upload|confirm|result)$/.test(v) ? 'check' : /^(record|doc)$/.test(v) ? 'record' : /^change/.test(v) ? 'changes' : /^contract/.test(v) ? 'contracts' : /^(schedule|delay|gantt)/.test(v) ? 'schedule' : v;
    document.querySelectorAll('[data-nav]').forEach(function (a) { var on = a.dataset.nav === navKey; if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
    document.body.classList.toggle('v-check', navKey === 'check' || v === 'contract' || v === 'contract-confirm');
    document.body.classList.toggle('v-field', v === 'field');
    var V = window.CSViews || {};
    if (V[v]) V[v](); else if (v === 'contract') viewContract(); else if (v === 'contract-confirm') viewContractConfirm(); else if (v === 'confirm') viewConfirm(); else if (v === 'result') viewResult(); else if (v === 'upload') viewUpload(); else go('home');
    if (v !== 'confirm') window.scrollTo(0, 0);
    requestAnimationFrame(frame);
    if (!/^contract/.test(v)) CS = null;
  }
  window.addEventListener('hashchange', route);

  var q = new URLSearchParams(location.search);
  setRole(q.get('role') || store('cs_role') || 'gc');
  Promise.all([
    fetch('/demo3/data/cases.json').then(function (r) { return r.json(); }),
    fetch('/api/extract', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
  ]).then(function (res) {
    res[0].cases.forEach(function (c) { cases[c.id] = c; });
    reader = res[1] && res[1].ok ? res[1].model : null;
    loadSession(); chip();
    if (q.get('sample') && cases[q.get('sample')]) { startSample(q.get('sample')); history.replaceState(null, '', location.pathname + '#result'); }
    route();
  }).catch(function () { app.innerHTML = '<div class="wrap"><div class="err">Could not load the checker. Refresh to try again.</div></div>'; });
})();
