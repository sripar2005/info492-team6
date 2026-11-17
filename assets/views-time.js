/* Schedule views for the check tool: load a schedule in any format, see its critical path and quality,
   edit it, keep baseline and update versions. The engine is assets/schedule.js; this file only draws and stores. */
(function () {
  'use strict';
  var A = window.CSApp, SE = window.ClauseSchedule, esc = A.esc, store = A.store, app = A.app;
  var V = window.CSViews = window.CSViews || {};
  // Washington legal holidays (RCW 1.16.050), observed. Offered for spreadsheet and PDF schedules, which carry no calendar.
  var WA_HOLIDAYS = ['2020-01-01', '2020-01-20', '2020-02-17', '2020-05-25', '2020-07-03', '2020-09-07', '2020-11-11', '2020-11-26', '2020-11-27', '2020-12-25',
    '2021-01-01', '2021-01-18', '2021-02-15', '2021-05-31', '2021-07-05', '2021-09-06', '2021-11-11', '2021-11-25', '2021-11-26', '2021-12-24',
    '2022-01-17', '2022-02-21', '2022-05-30', '2022-06-20', '2022-07-04', '2022-09-05', '2022-11-11', '2022-11-24', '2022-11-25', '2022-12-26'];
  var FORMAT = { xer: 'Primavera P6 (.xer)', mspdi: 'Microsoft Project XML', csv: 'CSV', xlsx: 'Excel', pdf: 'PDF (dates only)', manual: 'Edited here' };
  var SX = null; // schedule being confirmed: { model, file, raw, kind, opts, edited }

  function list() { return store('cs_schedules') || []; }
  function activeId() { return store('cs_sched_active'); }
  function active() { var id = activeId(); return list().filter(function (x) { return x.id === id; })[0] || list()[0] || null; }
  V.activeSchedule = active;
  function shortDate(d) { if (!d) return '—'; var x = new Date(d + 'T00:00:00Z'); return x.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }); }

  /* ---------- reading files ---------- */
  var sheetjs = null;
  function loadSheetJS() {
    if (sheetjs) return Promise.resolve(sheetjs);
    return new Promise(function (ok, no) { var s = document.createElement('script'); s.src = '/assets/vendor/sheetjs/xlsx.mini.min.js'; s.onload = function () { sheetjs = window.XLSX; ok(sheetjs); }; s.onerror = function () { no(new Error('Could not load the spreadsheet reader.')); }; document.head.appendChild(s); });
  }
  // PDF schedules have no logic. Rows are read from lines that look like "ID  Name  Duration  Start  Finish".
  var DATE = '(\\d{1,2}[-\\s][A-Za-z]{3}[-\\s]\\d{2,4}|\\d{4}-\\d{2}-\\d{2}|\\d{1,2}/\\d{1,2}/\\d{2,4})\\s*A?';
  var ROW = new RegExp('^\\s*([A-Z]{1,4}[-.]?\\d{2,6}[A-Z0-9.-]*)\\s+(.+?)\\s+(\\d+(?:\\.\\d+)?)\\s*d?(?:ays?)?\\s+' + DATE + '\\s+' + DATE);
  function pdfRows(text) {
    var rows = [['Activity ID', 'Activity Name', 'Original Duration', 'Start', 'Finish']];
    text.split(/\n/).forEach(function (line) { var m = ROW.exec(line.replace(/\s+/g, ' ')); if (m) rows.push([m[1], m[2], m[3], m[4], m[5]]); });
    return rows;
  }
  function needsOpts(kind) { return kind === 'csv' || kind === 'xlsx' || kind === 'pdf'; }
  function parse(raw, kind, opts) {
    var o = Object.assign({ format: kind }, opts);
    if (kind === 'xer') return SE.parseXER(raw, o);
    if (kind === 'mspdi') return SE.parseMSPDI(raw, o);
    if (kind === 'csv') return SE.parseCSV(raw, o);
    return SE.parseRows(raw, o); // xlsx rows or pdf rows
  }
  function openFile(file) {
    var n = file.name.toLowerCase(), kind = /\.xer$/.test(n) ? 'xer' : /\.xml$/.test(n) ? 'mspdi' : /\.csv$|\.txt$/.test(n) ? 'csv' : /\.xlsx?$|\.xlsm$/.test(n) ? 'xlsx' : /\.pdf$/.test(n) ? 'pdf' : null;
    if (/\.mpp$/.test(n)) return V.schedule('A .mpp file can’t be read in the browser. In Microsoft Project use File → Save As → XML, then load the .xml.');
    if (!kind) return V.schedule('Use a P6 .xer, a Microsoft Project .xml, a .csv, an Excel file or a PDF.');
    app.innerHTML = '<div class="wrap"><div class="reading"><div class="spinner"></div><h2>Opening ' + esc(file.name) + '…</h2></div></div>';
    var got = kind === 'xlsx' ? loadSheetJS().then(function (X) { return file.arrayBuffer().then(function (b) { var wb = X.read(b, { type: 'array', cellDates: false }); return X.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { header: 1, raw: true, defval: '' }); }); })
      : kind === 'pdf' ? A.pdfText(file).then(pdfRows) : file.text();
    got.then(function (raw) {
      if (kind === 'pdf' && raw.length < 3) return V.schedule('No activity rows found in that PDF. A scanned PDF has no text; try exporting the schedule to Excel or XML.');
      var opts = { name: file.name.replace(/\.[^.]+$/, ''), file: file.name, calendar: { workdays: [1, 2, 3, 4, 5], holidays: needsOpts(kind) ? WA_HOLIDAYS.slice() : undefined } };
      if (!needsOpts(kind)) delete opts.calendar;
      var model = parse(raw, kind, opts);
      SX = { model: model, file: file.name, raw: raw, kind: kind, opts: opts, label: 'Baseline', edited: false };
      A.go('schedule-confirm');
    }).catch(function (e) { V.schedule('Could not read ' + file.name + ': ' + e.message); });
  }

  /* ---------- list + upload ---------- */
  V.schedule = function (err) {
    var L = list(), act = active();
    var rows = L.map(function (x) {
      var c = SE.cpm(x.model);
      return '<tr data-sopen="' + esc(x.id) + '"><td><span class="t">' + esc(x.name) + '</span><span class="id">' + esc(FORMAT[x.model.source.format] || x.model.source.format) + ' · ' + x.model.activities.length + ' activities</span></td><td><span class="badge' + (x.label === 'Baseline' ? ' ok' : '') + '">' + esc(x.label) + '</span></td><td>' + shortDate(x.model.data_date) + '</td><td>' + shortDate(c.finish_date) + '</td><td>' + (act && act.id === x.id ? '<b>In use</b>' : '<button class="btn ghost sm" data-suse="' + esc(x.id) + '">Use</button>') + '</td></tr>';
    }).join('');
    app.innerHTML = '<div class="wrap">' +
      '<section class="upload"><span class="eyebrow">Schedules</span><h1 style="margin-top:10px">Load the project schedule</h1><p class="lede">The delay check needs the current schedule to see if a change is on the critical path and how many days it really adds.</p>' +
      '<div class="drop" id="sdrop"><div class="ic"></div><b>Drop a schedule here</b><p>Primavera P6 .xer · Microsoft Project .xml · Excel · CSV · PDF</p>' +
      '<label class="btn primary">Choose a file<input type="file" id="sfile" accept=".xer,.xml,.csv,.txt,.xlsx,.xls,.xlsm,.pdf" hidden></label>' +
      '<span class="or">or <button class="link" data-ssample="xer">try the sample schedule</button></span></div>' +
      (err ? '<div class="err">' + esc(err) + '</div>' : '') +
      '<div class="checks"><span>P6 and MS Project XML keep the logic</span><span>Excel and CSV keep it if there’s a predecessors column</span><span>PDF: dates only, critical path can’t be verified</span><span>.mpp: save as XML first</span></div></section>' +
      (L.length ? '<div class="card tbl-wrap" style="margin-top:34px"><table class="tbl"><thead><tr><th>Schedule</th><th>Version</th><th>Data date</th><th>Finish</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div><p class="fine">Kept in this browser only. The one in use is what the delay check runs against.</p>' : '') + '</div>';
    var drop = document.getElementById('sdrop');
    ['dragenter', 'dragover'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('over'); }); });
    ['dragleave', 'drop'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('over'); }); });
    drop.addEventListener('drop', function (e) { var f = e.dataTransfer.files[0]; if (f) openFile(f); });
    document.getElementById('sfile').addEventListener('change', function (e) { if (e.target.files[0]) openFile(e.target.files[0]); });
  };

  /* ---------- Gantt ---------- */
  function gantt(model, c, opts) {
    opts = opts || {};
    var acts = c.activities.slice(0, 400), byId = {}; acts.forEach(function (a) { byId[a.id] = a; });
    var dates = []; acts.forEach(function (a) { if (a.start) dates.push(a.start); if (a.finish) dates.push(a.finish); });
    if (!dates.length) return '<p class="fine">No dates to draw.</p>';
    dates.sort(); var t0 = Date.parse(dates[0]), t1 = Date.parse(dates[dates.length - 1]) + 864e5, span = Math.max(1, t1 - t0);
    var W = 1000, LBL = 0, rowH = 22, H = acts.length * rowH + 30;
    function x(d) { return LBL + (Date.parse(d) - t0) / span * (W - LBL); }
    var ticks = '', axis = '', d = new Date(t0), days = span / 864e5, weekly = days < 150;
    if (weekly) { while (d.getUTCDay() !== 1) d.setUTCDate(d.getUTCDate() + 1); } else { d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth() + 1); }
    var every = weekly ? (days > 70 ? 2 : 1) : (days > 900 ? 4 : days > 400 ? 3 : days > 200 ? 2 : 1);
    while (d.getTime() <= t1) {
      var xx = x(d.toISOString().slice(0, 10));
      ticks += '<line x1="' + xx + '" x2="' + xx + '" y1="0" y2="' + H + '" class="gt"/>';
      axis += '<span style="left:' + (xx / W * 100) + '%">' + d.toLocaleDateString('en-US', weekly ? { month: 'short', day: 'numeric', timeZone: 'UTC' } : { month: 'short', year: '2-digit', timeZone: 'UTC' }) + '</span>';
      if (weekly) d.setUTCDate(d.getUTCDate() + 7 * every); else d.setUTCMonth(d.getUTCMonth() + every);
    }
    var dd = model.data_date ? '<line x1="' + x(model.data_date) + '" x2="' + x(model.data_date) + '" y1="0" y2="' + H + '" class="gdd"/>' : '';
    var bars = acts.map(function (a, i) {
      var y = 24 + i * rowH, s = a.start || a.finish, f = a.finish || a.start; if (!s) return '';
      var cls = a.status === 'complete' ? 'done' : (opts.highlight && opts.highlight[a.id]) ? 'frag' : a.critical ? 'crit' : 'norm';
      var x0 = x(s), x1 = x(f) + (W / (span / 864e5));
      return a.duration === 0 ? '<path d="M' + x0 + ' ' + (y + 3) + 'l6 6-6 6-6-6z" class="g' + cls + '"><title>' + esc(a.id + ' ' + a.name + ' · ' + s) + '</title></path>'
        : '<rect x="' + x0 + '" y="' + (y + 4) + '" width="' + Math.max(2, x1 - x0) + '" height="12" rx="2" class="g' + cls + '"><title>' + esc(a.id + ' ' + a.name + ' · ' + s + ' → ' + f + (a.total_float != null ? ' · float ' + a.total_float : '')) + '</title></rect>';
    }).join('');
    var names = acts.map(function (a, i) { return '<div class="gn' + (a.critical ? ' crit' : '') + ((opts.highlight && opts.highlight[a.id]) ? ' frag' : '') + '" style="height:' + rowH + 'px"><code>' + esc(a.id) + '</code><span>' + esc(a.name) + '</span></div>'; }).join('');
    return '<div class="gantt"><div class="gnames" style="padding-top:' + (24 + 23) + 'px">' + names + '</div><div class="gchart"><div class="gaxis">' + axis + '</div><svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" style="height:' + H + 'px">' + ticks + dd + bars + '</svg></div></div>' +
      (c.activities.length > 400 ? '<p class="fine">Showing the first 400 of ' + c.activities.length + ' activities.</p>' : '') +
      '<div class="glegend"><span><i class="gcrit"></i>Critical path</span><span><i class="gnorm"></i>Has float</span><span><i class="gdone"></i>Complete</span>' + (opts.highlight ? '<span><i class="gfrag"></i>Change (fragnet)</span>' : '') + (model.data_date ? '<span><i class="gdd"></i>Data date</span>' : '') + '</div>';
  }
  V.gantt = gantt;

  /* ---------- confirm ---------- */
  V['schedule-confirm'] = function () {
    if (!SX) return A.go('schedule');
    var m = SX.model, c = SE.cpm(m), q = SE.quality(m), byId = {}; c.activities.forEach(function (a) { byId[a.id] = a; });
    var warns = (m.source.warnings || []).concat(c.warnings || []);
    var issues = q.filter(function (x) { return x.severity !== 'info'; });
    var cp = c.critical_path.map(function (id) { return '<li><code>' + esc(id) + '</code>' + esc(byId[id] ? byId[id].name : '') + '</li>'; }).join('');
    var opt = needsOpts(SX.kind) ? '<div class="card sec"><div class="sec-h"><h3>Calendar</h3><span class="tagr chk">this format has no calendar</span></div><div class="grid">' +
      '<div class="fd"><label><span>Data date <small>(status date)</small></span></label><div class="inp"><input type="date" data-so="data_date" value="' + esc(m.data_date || '') + '"></div></div>' +
      '<div class="fd"><label><span>Holidays</span></label><div class="inp sel"><select data-so="holidays"><option value="wa"' + (SX.opts.calendar.holidays.length ? ' selected' : '') + '>Washington legal holidays</option><option value="none"' + (SX.opts.calendar.holidays.length ? '' : ' selected') + '>None</option></select></div></div>' +
      '<div class="fd full"><label><span>Work days</span></label><div class="pills">' + ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(function (d, i) { return '<button class="pill" data-swd="' + i + '" aria-pressed="' + (SX.opts.calendar.workdays.indexOf(i) >= 0) + '">' + d + '</button>'; }).join('') + '</div></div></div></div>' : '';
    var h = '<div class="wrap"><div class="ph1"><div><span class="eyebrow">' + esc(SX.file || 'Schedule') + ' · ' + esc(FORMAT[m.source.format] || m.source.format) + '</span><h1 style="margin-top:8px">Check what we read</h1><p>Critical path recomputed from the logic in the file, not copied from it.</p></div></div>' +
      '<div class="cols result"><div><div class="paper sched">' + gantt(m, c) + '</div></div><div class="form">' +
      '<div class="card sec"><div class="kv"><div><span>Activities</span><b>' + m.activities.length + '</b></div><div><span>Links</span><b>' + m.relationships.length + '</b></div><div><span>Data date</span><b>' + shortDate(m.data_date) + '</b></div><div><span>Finish</span><b>' + shortDate(c.finish_date) + '</b></div></div>' +
      (m.source.has_logic ? '' : '<div class="banner warn" style="margin:14px 0 0">No logic in this file, so the critical path can’t be verified. The delay check will say so instead of guessing.</div>') + '</div>' + opt +
      (m.source.has_logic ? '<div class="card sec"><div class="sec-h"><h3>Critical path</h3><span class="tagr">' + c.critical_path.length + ' activities</span></div><ol class="cpath">' + cp + '</ol></div>' : '') +
      '<div class="card sec"><div class="sec-h"><h3>Schedule quality</h3><span class="tagr ' + (issues.length ? 'chk' : 'ok') + '">' + (issues.length ? issues.length + ' to look at' : 'no issues') + '</span></div><ul class="qual">' + q.map(function (x) {
        return '<li class="' + x.severity + '"><span class="qd"></span><div><b>' + esc(x.check) + (x.count ? ' · ' + x.count : '') + '</b>' + (x.count ? '<p>' + esc(x.note) + (x.ids && x.ids.length ? ' <code>' + esc(x.ids.slice(0, 8).join(', ')) + (x.ids.length > 8 ? '…' : '') + '</code>' : '') + '</p>' : '') + '</div></li>';
      }).join('') + '</ul>' + (warns.length ? '<details class="passed"><summary><span>' + warns.length + ' notes from reading the file</span><span>show ▾</span></summary><ul>' + warns.map(function (w) { return '<li><span>' + esc(w) + '</span></li>'; }).join('') + '</ul></details>' : '') + '</div>' +
      '<div class="card sec"><div class="sec-h"><h3>Edit activities</h3><span class="fine" style="margin:0">' + (SX.edited ? 'Edited here; the file is unchanged' : 'Fix a duration or a link; the critical path reruns') + '</span></div><div class="etbl"><table class="tbl"><thead><tr><th>ID</th><th>Name</th><th class="r">Days</th><th>Predecessors</th><th class="r">Float</th></tr></thead><tbody>' +
      m.activities.slice(0, 400).map(function (a, i) {
        var preds = m.relationships.filter(function (r) { return r.succ === a.id; }).map(function (r) { return r.pred + (r.type !== 'FS' || r.lag ? r.type : '') + (r.lag ? (r.lag > 0 ? '+' : '') + r.lag : ''); }).join(', ');
        var ca = byId[a.id] || {};
        return '<tr class="' + (ca.critical ? 'crit' : '') + '"><td><code>' + esc(a.id) + '</code></td><td>' + esc(a.name) + '</td><td class="r"><input class="ein" data-sdur="' + i + '" value="' + a.duration + '" inputmode="decimal"></td><td><input class="ein w" data-spred="' + i + '" value="' + esc(preds) + '" placeholder="e.g. A1010, A1020SS+2"></td><td class="r">' + (ca.total_float == null ? '—' : ca.total_float) + '</td></tr>';
      }).join('') + '</tbody></table></div></div>' +
      '<div class="card sec"><div class="grid"><div class="fd"><label><span>Name</span></label><div class="inp"><input id="sname" value="' + esc(SX.name || m.name || SX.opts.name || 'Schedule') + '"></div></div>' +
      '<div class="fd"><label><span>This version is the</span></label><div class="inp sel"><select id="slabel">' + ['Baseline', 'Update'].map(function (l) { return '<option' + (SX.label === l ? ' selected' : '') + '>' + l + '</option>'; }).join('') + '</select></div></div></div></div>' +
      '<div class="stick"><div class="live"><span>' + (m.source.has_logic ? 'Finish ' + shortDate(c.finish_date) + ' · ' + c.critical_path.length + ' on the critical path' : 'Dates only') + '</span></div><button class="btn ghost" data-go="schedule">Cancel</button><button class="btn primary" data-ssave="1">Use this schedule →</button></div>' +
      '</div></div></div>';
    app.innerHTML = h;
  };
  function keep(fn) { var y = window.scrollY; fn(); window.scrollTo(0, y); }
  function reparse() { SX.model = parse(SX.raw, SX.kind, SX.opts); if (SX.dataDate) SX.model.data_date = SX.dataDate; }

  app.addEventListener('change', function (e) {
    var t = e.target; if (!SX || location.hash !== '#schedule-confirm') return;
    if (t.dataset.so === 'data_date') { SX.opts.data_date = t.value || null; SX.model.data_date = t.value || null; return keep(V['schedule-confirm']); }
    if (t.dataset.so === 'holidays') { SX.opts.calendar.holidays = t.value === 'wa' ? WA_HOLIDAYS.slice() : []; reparse(); return keep(V['schedule-confirm']); }
    if (t.dataset.sdur != null) { var a = SX.model.activities[+t.dataset.sdur], v = parseFloat(t.value); if (isFinite(v) && v >= 0) { a.duration = v; if (a.remaining != null) a.remaining = Math.min(a.remaining, v); SX.edited = true; } return keep(V['schedule-confirm']); }
    if (t.dataset.spred != null) {
      var id = SX.model.activities[+t.dataset.spred].id, ps;
      try { ps = SE.parsePredecessors(t.value); } catch (er) { return A.toast('Couldn’t read those predecessors. Use ids like A1010 or A1020SS+2.'); }
      SX.model.relationships = SX.model.relationships.filter(function (r) { return r.succ !== id; }).concat(ps.map(function (p) { return { pred: p.pred, succ: id, type: p.type, lag: p.lag }; }));
      if (ps.length) SX.model.source.has_logic = true; SX.edited = true; return keep(V['schedule-confirm']);
    }
  });
  app.addEventListener('click', function (e) {
    var t = e.target.closest('[data-ssample],[data-sopen],[data-suse],[data-ssave],[data-swd]'); if (!t) return;
    if (t.dataset.ssample) { fetch('/demo4/data/schedule.xer').then(function (r) { if (!r.ok) return fetch('/tools/fixtures/school.xer'); return r; }).then(function (r) { return r.text(); }).then(function (txt) { openFile(new File([txt], 'sample-schedule.xer')); }); return; }
    if (t.dataset.suse) { e.stopPropagation(); store('cs_sched_active', t.dataset.suse); A.toast('Delay checks now use this schedule.'); return V.schedule(); }
    if (t.dataset.sopen) { var x = list().filter(function (s) { return s.id === t.dataset.sopen; })[0]; if (!x) return; SX = { model: x.model, file: x.file, raw: null, kind: 'manual', opts: { calendar: x.model.calendar }, label: x.label, name: x.name, id: x.id, edited: false }; return A.go('schedule-confirm'); }
    if (t.dataset.swd != null) { var w = SX.opts.calendar.workdays, i = +t.dataset.swd, k = w.indexOf(i); if (k >= 0) w.splice(k, 1); else w.push(i); w.sort(); reparse(); return keep(V['schedule-confirm']); }
    if (t.dataset.ssave) {
      var name = (document.getElementById('sname').value || '').trim() || 'Schedule', label = document.getElementById('slabel').value;
      if (SX.edited) SX.model.source = Object.assign({}, SX.model.source, { edited: true });
      var rec = { id: SX.id || 's' + Date.now().toString(36), name: name, label: label, file: SX.file, saved: Date.now(), model: SX.model };
      var L = list().filter(function (s) { return s.id !== rec.id; }); L.unshift(rec);
      try { store('cs_schedules', L.slice(0, 8)); } catch (er) { return A.toast('This browser’s storage is full. Remove an old schedule first.'); }
      if (!store('cs_schedules') || !store('cs_schedules').length) return A.toast('This schedule is too large to keep in the browser.');
      store('cs_sched_active', rec.id); SX = null; A.toast('Delay checks now use “' + name + '”.'); return A.go('schedule');
    }
  });
})();

/* Delay check: a change order's time claim -> fragnet -> time impact analysis in code -> what the contract pays.
   Every step goes in an audit log tagged AI-proposed, computed, or person-confirmed. */
(function () {
  'use strict';
  var A = window.CSApp, SE = window.ClauseSchedule, D = window.ClauseDelay, esc = A.esc, store = A.store, app = A.app, M = A.M;
  var V = window.CSViews;
  var DX = null; // { claim, frag: {activities, relationships}, fragSrc, result, cond, chosen, log: [] }
  var PARTY = [['owner', 'Owner'], ['architect', 'Architect'], ['contractor', 'Contractor'], ['neither', 'Neither (e.g. weather)']];
  var cases = null, saved = null;
  function loadSaved() {
    if (saved) return Promise.resolve(saved);
    return fetch('/demo4/results/fragnet_runs.json').then(function (r) { return r.ok ? r.json() : null; }).then(function (j) { saved = j || { cases: [] }; return saved; }).catch(function () { saved = { cases: [] }; return saved; });
  }

  function log(who, text) { DX.log.push({ at: new Date().toISOString(), who: who, text: text }); }
  function blank() { return { claim: { id: '', title: '', claimed_days: 0, claimed_unit: 'calendar', narrative: '', cause_party: 'owner', concurrent: false, claimed_cost: null, claimed_rate: null, sgc_also: false },
    frag: { activities: [], relationships: [] }, fragSrc: null, result: null, cond: null, chosen: null, log: [], step: 1 }; }
  function sched() { return V.activeSchedule(); }

  function loadCases() {
    if (cases) return Promise.resolve(cases);
    return fetch('/demo4/data/cases.json').then(function (r) { return r.ok ? r.json() : { cases: [] }; }).then(function (j) { cases = (j.cases || []).filter(function (c) { return c.time; }); return cases; }).catch(function () { cases = []; return cases; });
  }
  function fromCase(c) {
    var d = blank(), cs = c.cover_sheet || {};
    d.claim = { id: c.id, title: c.title, claimed_days: c.time.claimed_days || c.time_impact_days || 0, claimed_unit: c.time.claimed_calendar === false ? 'work' : 'calendar', narrative: c.time.narrative || '', cause_party: c.time.cause_party || 'owner',
      concurrent: !!c.time.concurrent, claimed_cost: cs.extended_sgc_time || null, claimed_rate: c.time.claimed_rate || null, sgc_also: !!(cs.sgc_items && cs.extended_sgc_time) };
    d.caseId = c.id; return d;
  }

  /* ---------- step 1: the claim ---------- */
  V.delay = function () {
    var s = sched();
    if (!DX) DX = blank();
    loadCases().then(function (cs) {
      var c = DX.claim;
      var pick = cs.length ? '<div class="samples" style="justify-content:flex-start;margin:0 0 16px">Sample change orders:' + cs.slice(0, 8).map(function (x) { return '<button data-dcase="' + esc(x.id) + '">' + esc(x.id) + '</button>'; }).join('') + '</div>' : '';
      app.innerHTML = '<div class="wrap"><div class="ph1"><div><span class="eyebrow">Delay check</span><h1 style="margin-top:8px">Is the time claim real, and what is it worth?</h1><p>We add the change’s work to the current schedule, rerun the critical path, and price the days the contract allows.</p></div></div>' +
        (s ? '<div class="banner"><span>Schedule: <b>' + esc(s.name) + '</b> (' + esc(s.label) + ', ' + s.model.activities.length + ' activities). Contract: <b>' + esc(A.C().name) + '</b>. <a class="link" href="#schedule">Change</a></span></div>'
          : '<div class="banner warn"><span>No schedule loaded yet. <a class="link" href="#schedule">Load the schedule</a> first; the delay check runs against it.</span></div>') +
        '<div class="cols"><div class="form">' + pick +
        '<div class="card sec"><div class="sec-h"><h3>The time claim</h3></div><div class="grid">' +
        fld('id', 'Change order', c.id, 'e.g. CO-0407') + '<div class="fd"><label><span>Days claimed</span></label><div style="display:flex;gap:8px"><div class="inp" style="flex:1"><input data-dc="claimed_days" inputmode="decimal" data-num="1" value="' + esc(c.claimed_days == null ? '' : c.claimed_days) + '"></div><div class="inp sel" style="flex:1.3"><select data-dc="claimed_unit"><option value="calendar"' + (c.claimed_unit !== 'work' ? ' selected' : '') + '>calendar days</option><option value="work"' + (c.claimed_unit === 'work' ? ' selected' : '') + '>working days</option></select></div></div></div>' +
        '<div class="fd full"><label><span>What happened <small>(the narrative from the change order)</small></span></label><div class="inp" style="height:auto"><textarea data-dc="narrative" rows="4" placeholder="e.g. Owner added a second elevator; shop drawings and install add about 3 weeks to the elevator work.">' + esc(c.narrative) + '</textarea></div></div>' +
        '<div class="fd"><label><span>Who caused it</span></label><div class="inp sel"><select data-dc="cause_party">' + PARTY.map(function (p) { return '<option value="' + p[0] + '"' + (p[0] === c.cause_party ? ' selected' : '') + '>' + p[1] + '</option>'; }).join('') + '</select></div></div>' +
        '<div class="fd"><label><span>Concurrent delay?</span></label><div class="inp sel"><select data-dc="concurrent"><option value="false"' + (c.concurrent ? '' : ' selected') + '>No</option><option value="true"' + (c.concurrent ? ' selected' : '') + '>Yes, another delay overlaps</option></select></div></div>' +
        fld('claimed_cost', 'Extended general conditions asked', c.claimed_cost, '', '$', true) + fld('claimed_rate', 'Daily rate used in the claim', c.claimed_rate, 'if stated', '$/day', true) +
        '</div></div>' +
        '<div class="stick"><div class="live"><span>Next: describe the change’s work in the schedule</span></div><button class="btn primary" data-dnext="2"' + (s ? '' : ' disabled') + '>Next: the change’s activities →</button></div></div>' +
        '<div><div class="card sec how2"><h3 style="font-size:14.5px;margin-bottom:10px">How the days are worked out</h3><ol class="how" style="margin:0"><li><b>You or the AI</b> describe the change’s work as a few activities linked into the schedule (a “fragnet”). The AI may only link to activity IDs that exist.</li><li><b>Code</b> inserts them into the current schedule and reruns the critical path (AACE 52R-06 time impact analysis).</li><li><b>Code</b> compares the finish dates. Off the critical path, the delay is 0.</li><li><b>Code</b> prices the days under the contract; the slider shows the range when conditions are unclear.</li><li><b>You</b> confirm. Every step is logged.</li></ol></div></div></div></div>';
    });
  };
  function fld(k, label, v, ph, unit, numeric) {
    var pre = unit === '$' || unit === '$/day' ? '<span class="pre">$</span>' : '', suf = unit && unit !== '$' ? '<span class="suf">' + (unit === '$/day' ? '/day' : unit) + '</span>' : '';
    return '<div class="fd"><label><span>' + label + '</span></label><div class="inp">' + pre + '<input data-dc="' + k + '"' + (numeric ? ' inputmode="decimal" data-num="1"' : '') + ' value="' + esc(v == null ? '' : v) + '"' + (ph ? ' placeholder="' + esc(ph) + '"' : '') + '>' + suf + '</div></div>';
  }

  /* ---------- step 2: fragnet ---------- */
  function fragHtml() {
    var s = sched(), ids = s.model.activities.map(function (a) { return a.id; }), F = DX.frag;
    var dl = '<datalist id="actids">' + s.model.activities.map(function (a) { return '<option value="' + esc(a.id) + '">' + esc(a.name) + '</option>'; }).join('') + F.activities.map(function (a) { return '<option value="' + esc(a.id) + '">' + esc(a.name) + '</option>'; }).join('') + '</datalist>';
    var rows = F.activities.map(function (a, i) {
      var after = F.relationships.filter(function (r) { return r.succ === a.id; }).map(function (r) { return r.pred + (r.type !== 'FS' ? r.type : '') + (r.lag ? (r.lag > 0 ? '+' : '') + r.lag : ''); }).join(', ');
      var before = F.relationships.filter(function (r) { return r.pred === a.id; }).map(function (r) { return r.succ + (r.type !== 'FS' ? r.type : '') + (r.lag ? (r.lag > 0 ? '+' : '') + r.lag : ''); }).join(', ');
      return '<tr><td><code>' + esc(a.id) + '</code></td><td><input class="ein w" data-fa="' + i + '|name" value="' + esc(a.name) + '" style="font-family:var(--sans)"></td><td class="r"><input class="ein" data-fa="' + i + '|duration" value="' + a.duration + '"></td>' +
        '<td><input class="ein w" list="actids" data-fl="' + i + '|after" value="' + esc(after) + '" placeholder="starts after…"></td><td><input class="ein w" list="actids" data-fl="' + i + '|before" value="' + esc(before) + '" placeholder="must finish before…"></td><td><button class="del" data-fdel="' + i + '" aria-label="Remove">✕</button></td></tr>';
    }).join('');
    var bad = F.relationships.filter(function (r) { var all = ids.concat(F.activities.map(function (a) { return a.id; })); return all.indexOf(r.pred) < 0 || all.indexOf(r.succ) < 0; });
    return dl + '<div class="etbl" style="margin:0;max-height:none"><table class="tbl"><thead><tr><th>ID</th><th>Activity</th><th class="r">Work days</th><th>After</th><th>Before</th><th></th></tr></thead><tbody>' + (rows || '<tr><td colspan="6" class="fine" style="padding:14px">No activities yet.</td></tr>') + '</tbody></table></div>' +
      (bad.length ? '<p class="hint" style="color:var(--red)">Links to IDs not in the schedule: ' + esc(bad.map(function (r) { return r.pred + '→' + r.succ; }).join(', ')) + '</p>' : '') +
      '<button class="btn ghost sm add" data-fadd="1" style="margin-top:10px">+ Activity</button>';
  }
  V['delay-fragnet'] = function () {
    if (!DX || !sched()) return A.go('delay');
    var reader = A.reader(), s = sched();
    if (!saved) { loadSaved().then(function () { V['delay-fragnet'](); }); return; }
    var run = DX.caseId && saved.cases.filter(function (x) { return x.id === DX.caseId && x.fragnet && x.fragnet.activities.length; })[0];
    var src = DX.fragSrc === 'ai' ? '<div class="banner"><span><b>Drafted by ' + esc(DX.fragModel || 'the local model') + '</b>' + (DX.fragAgree === false ? ' — its three drafts <b>disagreed</b>, so look closely.' : DX.fragAgree ? '; its three drafts agreed.' : '.') + ' It could only link to IDs in this schedule. Check the durations and links against the change order.' + (DX.fragNotes && DX.fragNotes.length ? '<br>' + DX.fragNotes.map(esc).join('<br>') : '') + '</span></div>' : '';
    app.innerHTML = '<div class="wrap"><div class="ph1"><div><span class="eyebrow">Delay check · ' + esc(DX.claim.id || 'change order') + ' · step 2 of 3</span><h1 style="margin-top:8px">The change’s activities</h1><p>Add the work the change creates and where it sits in the schedule. Durations in work days.</p></div>' +
      '<div style="display:flex;gap:8px">' + (run && DX.fragSrc !== 'ai' ? '<button class="btn" data-fsaved="1">Use the saved AI draft</button>' : '') + (reader ? '<button class="btn" data-fdraft="1">Draft with ' + esc(reader) + '</button>' : '') + '</div></div>' +
      '<div class="cols result"><div><div class="paper sched" id="fgantt"></div></div><div class="form">' +
      (DX.claim.narrative ? '<div class="card sec"><span class="eyebrow">From the change order</span><p style="margin:8px 0 0;color:var(--muted);font-size:13.5px">' + esc(DX.claim.narrative) + '</p></div>' : '') + src +
      '<div class="card sec"><div class="sec-h"><h3>Fragnet</h3><span class="fine" style="margin:0">IDs start with F-</span></div>' + fragHtml() + '</div>' +
      (reader ? '' : '<p class="fine">The AI drafter runs on the team’s laptop. Here, enter the activities yourself.</p>') +
      '<div class="stick"><div class="live" id="flive"></div><button class="btn ghost" data-dnext="1">← Back</button><button class="btn primary" data-dnext="3"' + (DX.frag.activities.length ? '' : ' disabled') + '>Run the analysis →</button></div></div></div></div>';
    drawFragGantt();
  };
  function withFrag(model, F) {
    var m = JSON.parse(JSON.stringify(model)), ids = {}; m.activities.forEach(function (a) { ids[a.id] = 1; });
    F.activities.forEach(function (f) { m.activities.push({ id: f.id, name: f.name, duration: +f.duration || 0, wbs: 'Change', actual_start: null, actual_finish: null, remaining: null, constraint: null }); ids[f.id] = 1; });
    F.relationships.forEach(function (r) { if (ids[r.pred] && ids[r.succ]) m.relationships.push({ pred: r.pred, succ: r.succ, type: r.type || 'FS', lag: +r.lag || 0 }); });
    return m;
  }
  function drawFragGantt() {
    var el = document.getElementById('fgantt'), s = sched(); if (!el) return;
    var m = withFrag(s.model, DX.frag), c = SE.cpm(m), hl = {}; DX.frag.activities.forEach(function (a) { hl[a.id] = 1; });
    el.innerHTML = V.gantt(m, c, { highlight: hl });
    var r = DX.frag.activities.length ? SE.tia(s.model, DX.frag) : null, lv = document.getElementById('flive');
    if (lv) lv.innerHTML = r ? '<span>Preview: finish moves <b>' + r.delay_calendar_days + ' calendar days</b> · claimed ' + (DX.claim.claimed_days || 0) + '</span>' : '<span>Add the change’s activities to preview the impact.</span>';
  }
  function nextFid() { var n = 1, have = DX.frag.activities.map(function (a) { return a.id; }); while (have.indexOf('F-' + n) >= 0) n++; return 'F-' + n; }
  function setLinks(i, side, text) {
    var id = DX.frag.activities[i].id, ps = SE.parsePredecessors(text);
    DX.frag.relationships = DX.frag.relationships.filter(function (r) { return side === 'after' ? r.succ !== id : r.pred !== id; })
      .concat(ps.map(function (p) { return side === 'after' ? { pred: p.pred, succ: id, type: p.type, lag: p.lag } : { pred: id, succ: p.pred, type: p.type, lag: p.lag }; }));
  }
  function draftWithAI() {
    var s = sched(), t0 = Date.now();
    app.innerHTML = '<div class="wrap"><div class="reading"><div class="spinner"></div><h2>Drafting the change’s activities</h2><p class="fine" style="font-size:13.5px">' + esc(A.reader()) + ' drafts three times; you’ll see if the drafts disagree. <span id="tick">0:00</span></p></div></div>';
    var tick = setInterval(function () { var x = Math.round((Date.now() - t0) / 1000), el = document.getElementById('tick'); if (el) el.textContent = Math.floor(x / 60) + ':' + ('0' + x % 60).slice(-2); }, 1000);
    fetch('/api/fragnet', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ narrative: DX.claim.narrative, claimed_days: DX.claim.claimed_days, activities: s.model.activities.map(function (a) { return { id: a.id, name: a.name, duration: a.duration, wbs: a.wbs }; }), critical: SE.cpm(s.model).critical_path, runs: 3 }) })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || 'HTTP ' + r.status); return j; }); })
      .then(function (j) {
        clearInterval(tick); DX.frag = j.fragnet; DX.fragSrc = 'ai'; DX.fragModel = j.model; DX.fragAgree = j.agree; DX.fragNotes = j.notes || [];
        log('ai', j.model + ' drafted ' + j.fragnet.activities.length + ' activities: ' + j.fragnet.activities.map(function (a) { return a.id + ' ' + a.name + ' (' + a.duration + 'd)'; }).join('; ') + '. Links: ' + j.fragnet.relationships.map(function (r) { return r.pred + '→' + r.succ + (r.type !== 'FS' ? ' ' + r.type : ''); }).join(', ') + '. ' + (j.agree ? 'The three drafts agreed.' : 'The three drafts disagreed: ' + (j.disagreement || '') ));
        A.go('delay-fragnet'); V['delay-fragnet']();
      })
      .catch(function (e) { clearInterval(tick); A.toast('The local model couldn’t draft it (' + e.message + '). Enter the activities yourself.'); V['delay-fragnet'](); });
  }

  /* ---------- step 3: result ---------- */
  function cond() { var c = DX.claim; return DX.cond || (DX.cond = { causeParty: c.cause_party, compensable: null, concurrent: !!c.concurrent }); }
  V['delay-result'] = function () {
    if (!DX || !DX.result) return A.go('delay');
    var s = sched(), r = DX.result, C = A.C(), k = cond(), c = DX.claim;
    var d = D.delayCheck(C, { computedDays: r.delay_calendar_days, computedWorkDays: r.delay_workdays, claimedUnit: c.claimed_unit, claimedDays: +c.claimed_days || 0, onCriticalPath: r.delay_calendar_days > 0 || r.fragnet_critical, causeParty: k.causeParty, compensable: k.compensable, concurrent: k.concurrent,
      claimedCost: c.claimed_cost ? +c.claimed_cost : null, claimedRate: c.claimed_rate ? +c.claimed_rate : null, sgcAlsoBilled: !!c.sgc_also });
    if (!s.model.source.has_logic) d.flags.unshift({ flag: 'NO_LOGIC', severity: 'person', text: 'This schedule has no logic (dates only), so the impact can’t be verified from it.', section: '' });
    DX.check = d;
    var lo = d.cost.low || 0, hi = d.cost.high || 0, val = DX.chosen == null ? (d.cost.point != null ? d.cost.point : hi) : Math.min(hi, Math.max(lo, DX.chosen));
    var m = withFrag(s.model, DX.frag), cc = SE.cpm(m), hl = {}; DX.frag.activities.forEach(function (a) { hl[a.id] = 1; });
    var cmpDays = c.claimed_unit === 'work' ? r.delay_workdays : r.delay_calendar_days, padded = (+c.claimed_days || 0) > cmpDays;
    var head = r.delay_calendar_days === 0 ? 'The change doesn’t move the finish' : padded ? 'Supports ' + cmpDays + ' of ' + c.claimed_days + (c.claimed_unit === 'work' ? ' working' : '') + ' days claimed' : (+c.claimed_days ? 'Supports the ' + c.claimed_days + (c.claimed_unit === 'work' ? ' working' : '') + ' days claimed' : 'The change moves the finish ' + r.delay_calendar_days + ' days');
    var tone = r.delay_calendar_days === 0 && c.claimed_days > 0 ? 'fail' : padded ? 'fail' : 'ok';
    var tg = function (on, k2, v, label) { return '<button class="pill" data-dk="' + k2 + '|' + v + '" aria-pressed="' + on + '">' + label + '</button>'; };
    var h = '<div class="wrap"><div class="ph1"><div><span class="eyebrow">Delay check · ' + esc(c.id || 'change order') + ' · step 3 of 3</span><h1 style="margin-top:8px">Result</h1></div><div style="display:flex;gap:8px"><button class="btn ghost" data-dnext="2">← Edit activities</button><button class="btn" data-dexport="1">Export audit log</button></div></div>' +
      '<div class="cols result"><div><div class="paper sched">' + V.gantt(m, cc, { highlight: hl }) + '</div>' +
      '<div class="tblock" style="margin-top:12px"><div><span>Finish before</span><b>' + esc(r.before_finish) + '</b></div><div><span>Finish after</span><b>' + esc(r.after_finish) + '</b></div><div><span>Delay</span><b>' + r.delay_calendar_days + ' cal · ' + r.delay_workdays + ' work days</b></div><div><span>Change on critical path</span><b>' + (r.fragnet_critical ? 'Yes' : 'No') + '</b></div></div></div>' +
      '<div class="card findings"><div class="verdict ' + tone + '"><span class="eyebrow">Time impact analysis · computed</span><h2><em>' + esc(head) + '</em></h2><p>' + esc(r.notes[0] || '') + '</p></div>' +
      '<div class="dcost"><div class="sec-h" style="margin:0 0 10px"><h3>What the contract pays</h3><span class="tagr">' + d.extensionDays + ' days extension</span></div>' +
      '<div class="conds"><div><span>Who caused it</span><div class="pills">' + PARTY.map(function (p) { return tg(k.causeParty === p[0], 'causeParty', p[0], p[1].split(' (')[0]); }).join('') + '</div></div>' +
      '<div><span>Paid or time only</span><div class="pills">' + tg(k.compensable === null, 'compensable', 'null', 'As the contract says') + tg(k.compensable === true, 'compensable', 'true', 'Paid') + tg(k.compensable === false, 'compensable', 'false', 'Time only') + '</div></div>' +
      '<div><span>Concurrent delay</span><div class="pills">' + tg(!k.concurrent, 'concurrent', 'false', 'No') + tg(k.concurrent, 'concurrent', 'true', 'Yes') + '</div></div></div>' +
      (hi > 0 ? '<div class="slider"><div class="sv"><b>' + M(val) + '</b><span>' + (lo === hi ? 'fixed by the contract' : 'range ' + M(lo) + ' – ' + M(hi)) + '</span></div>' +
        (lo !== hi ? '<input type="range" id="dslide" min="' + lo + '" max="' + hi + '" step="1" value="' + val + '">' : '<div class="sbar"></div>') +
        '<p class="fine">' + d.paidDays[0] + (d.paidDays[1] !== d.paidDays[0] ? '–' + d.paidDays[1] : '') + ' paid days × ' + (d.rate.low !== d.rate.high ? M(d.rate.low) + '–' + M(d.rate.high) : M(d.rate.value)) + '/day' + (c.claimed_cost ? ' · asked ' + M(+c.claimed_cost) : '') + '</p></div>'
        : '<div class="slider"><div class="sv"><b>' + M(0) + '</b><span>' + (d.extensionDays ? 'time only: days, no money' : 'no paid delay') + '</span></div>' + (d.ldExposure ? '<p class="fine">Liquidated damages exposure: ' + M(d.ldExposure) + '</p>' : '') + '</div>') +
      '</div>' +
      (d.flags.length ? '<ol class="fl">' + d.flags.map(function (f, i) { return '<li class="' + (f.severity === 'fail' ? 'fail' : 'person') + '"><span class="n">' + (i + 1) + '</span><div><b>' + esc(f.text) + '</b>' + (f.section ? '<p>§ ' + esc(f.section) + '</p>' : '') + '</div></li>'; }).join('') + '</ol>' : '') +
      '<details class="passed" open><summary><span style="color:var(--text)">Audit log · ' + (DX.log.length + d.steps.length) + ' entries</span><span>hide ▴</span></summary><ul class="audit">' +
      DX.log.concat(d.steps.map(function (x) { return { who: x.who, text: x.text }; })).map(function (x) { return '<li><span class="who ' + x.who + '">' + ({ ai: 'AI proposed', computed: 'Computed', person: 'Person' }[x.who] || x.who) + '</span><span>' + esc(x.text) + '</span></li>'; }).join('') + '</ul></details>' +
      '<div class="acts"><button class="btn primary" data-dapprove="1">Confirm this result</button><button class="btn ghost" data-dnew="1">Check another</button></div></div></div></div>';
    app.innerHTML = h;
    var sl = document.getElementById('dslide');
    if (sl) sl.addEventListener('input', function () { DX.chosen = +sl.value; sl.parentNode.querySelector('.sv b').textContent = M(+sl.value); });
  };
  function runTIA() {
    var s = sched(); DX.result = SE.tia(s.model, DX.frag); DX.cond = null; DX.chosen = null;
    if (DX.fragSrc !== 'ai' || DX.fragEdited) log('person', 'Fragnet ' + (DX.fragSrc === 'ai' ? 'edited and confirmed' : 'entered') + ': ' + DX.frag.activities.map(function (a) { return a.id + ' ' + a.name + ' (' + a.duration + 'd)'; }).join('; ') + '.');
    else log('person', 'AI fragnet confirmed without changes.');
    log('computed', 'TIA on "' + s.name + '" (data date ' + (s.model.data_date || '—') + '): ' + DX.result.notes.join(' '));
  }
  function exportLog() {
    var c = DX.claim, d = DX.check, lines = ['ClauseStream delay check', 'Change order: ' + (c.id || '—') + ' ' + (c.title || ''), 'Schedule: ' + sched().name, 'Contract: ' + A.C().name, 'Exported: ' + new Date().toISOString(), ''];
    DX.log.concat(d.steps).forEach(function (x) { lines.push('[' + ({ ai: 'AI proposed', computed: 'Computed', person: 'Person' }[x.who]) + '] ' + x.text); });
    if (d.flags.length) { lines.push('', 'Flags:'); d.flags.forEach(function (f) { lines.push('- ' + f.text + (f.section ? ' (§ ' + f.section + ')' : '')); }); }
    var blob = new Blob([lines.join('\n') + '\n'], { type: 'text/plain' }), a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'delay-check-' + (c.id || 'co') + '.txt'; document.body.appendChild(a); a.click(); a.remove();
  }
  function approve() {
    var d = DX.check, c = DX.claim;
    log('person', 'Confirmed: ' + d.extensionDays + ' days extension, ' + M(DX.chosen != null ? DX.chosen : (d.cost.point != null ? d.cost.point : d.cost.high || 0)) + ' for delay.');
    var m = document.createElement('div'); m.className = 'modal';
    m.innerHTML = '<div class="modal-card" style="width:min(480px,100%)"><div class="modal-h"><div><span class="eyebrow">Result confirmed</span><h2>Update the schedule too?</h2></div></div><p style="color:var(--muted);margin:0 0 16px">Save a new update of “' + esc(sched().name) + '” with ' + esc(c.id || 'this change') + '’s activities in it, so the next delay check builds on it. The current version is kept.</p><div class="acts" style="margin:0"><button class="btn primary" data-up="yes">Save as a schedule update</button><button class="btn ghost" data-up="no">Not now</button></div></div>';
    document.body.appendChild(m);
    m.addEventListener('click', function (e) {
      var b = e.target.closest('[data-up]'); if (!b && e.target !== m) return;
      if (b && b.dataset.up === 'yes') {
        var s = sched(), nm = withFrag(s.model, DX.frag); nm.source = Object.assign({}, s.model.source, { edited: true });
        var rec = { id: 's' + Date.now().toString(36), name: s.name + ' + ' + (c.id || 'change'), label: 'Update', file: s.file, saved: Date.now(), model: nm };
        var L = store('cs_schedules') || []; L.unshift(rec); store('cs_schedules', L.slice(0, 8)); store('cs_sched_active', rec.id);
        log('person', 'Saved schedule update "' + rec.name + '" and made it the one in use.'); A.toast('Schedule updated. The delay check now uses “' + rec.name + '”.');
      } else A.toast('Result confirmed. Export the audit log to keep a copy.');
      m.remove(); V['delay-result']();
    });
  }

  app.addEventListener('input', function (e) {
    var t = e.target; if (!DX) return;
    if (t.dataset.dc) { var v = t.value; DX.claim[t.dataset.dc] = t.dataset.num ? (v.trim() === '' ? null : A.num(v)) : t.tagName === 'SELECT' && (v === 'true' || v === 'false') ? v === 'true' : v; }
  });
  app.addEventListener('change', function (e) {
    var t = e.target; if (!DX) return;
    if (t.dataset.dc && t.tagName === 'SELECT') { var v = t.value; DX.claim[t.dataset.dc] = v === 'true' ? true : v === 'false' ? false : v; }
    if (t.dataset.fa) { var p = t.dataset.fa.split('|'), a = DX.frag.activities[+p[0]]; a[p[1]] = p[1] === 'duration' ? Math.max(0, A.num(t.value)) : t.value; DX.fragEdited = true; drawFragGantt(); }
    if (t.dataset.fl) { var q = t.dataset.fl.split('|'); try { setLinks(+q[0], q[1], t.value); } catch (er) { A.toast('Use activity IDs like A1040, or A1040SS+2.'); } DX.fragEdited = true; var y = window.scrollY; V['delay-fragnet'](); window.scrollTo(0, y); }
  });
  app.addEventListener('click', function (e) {
    var t = e.target.closest('[data-dcase],[data-dnext],[data-fadd],[data-fdel],[data-fdraft],[data-fsaved],[data-dk],[data-dexport],[data-dapprove],[data-dnew]'); if (!t) return;
    if (t.dataset.dcase) { var x = cases.filter(function (c) { return c.id === t.dataset.dcase; })[0]; DX = fromCase(x); return V.delay(); }
    if (t.dataset.dnext) {
      var n = t.dataset.dnext;
      if (n === '2') { log('person', 'Claim entered: ' + (DX.claim.id || 'change order') + ', ' + (DX.claim.claimed_days || 0) + ' ' + (DX.claim.claimed_unit === 'work' ? 'working' : 'calendar') + ' days claimed, caused by ' + DX.claim.cause_party + (DX.claim.concurrent ? ', concurrent delay' : '') + '.'); return A.go('delay-fragnet'); }
      if (n === '3') { runTIA(); return A.go('delay-result'); }
      return A.go(n === '1' ? 'delay' : 'delay-fragnet');
    }
    if (t.dataset.fadd) { DX.frag.activities.push({ id: nextFid(), name: '', duration: 5 }); DX.fragEdited = true; return V['delay-fragnet'](); }
    if (t.dataset.fdel) { var id = DX.frag.activities[+t.dataset.fdel].id; DX.frag.activities.splice(+t.dataset.fdel, 1); DX.frag.relationships = DX.frag.relationships.filter(function (r) { return r.pred !== id && r.succ !== id; }); DX.fragEdited = true; return V['delay-fragnet'](); }
    if (t.dataset.fdraft) return draftWithAI();
    if (t.dataset.fsaved) {
      var run = saved.cases.filter(function (x) { return x.id === DX.caseId; })[0];
      DX.frag = JSON.parse(JSON.stringify(run.fragnet)); DX.fragSrc = 'ai'; DX.fragModel = saved.meta.model + ', saved run ' + saved.meta.date; DX.fragAgree = run.agreed; DX.fragNotes = run.notes || []; DX.fragEdited = false;
      log('ai', saved.meta.model + ' drafted (saved run, ' + saved.meta.date + '): ' + run.fragnet.activities.map(function (a) { return a.id + ' ' + a.name + ' (' + a.duration + 'd)'; }).join('; ') + '. ' + (run.agreed ? 'The drafts agreed.' : 'The drafts disagreed.'));
      return V['delay-fragnet']();
    }
    if (t.dataset.dk) { var kv = t.dataset.dk.split('|'), k = cond(); k[kv[0]] = kv[1] === 'null' ? null : kv[1] === 'true' ? true : kv[1] === 'false' ? false : kv[1]; DX.chosen = null; log('person', 'Condition set: ' + kv[0] + ' = ' + kv[1] + '.'); var y = window.scrollY; V['delay-result'](); window.scrollTo(0, y); return; }
    if (t.dataset.dexport) return exportLog();
    if (t.dataset.dapprove) return approve();
    if (t.dataset.dnew) { DX = null; return A.go('delay'); }
  });
})();
