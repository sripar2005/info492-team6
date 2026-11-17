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
    var every = weekly ? (days > 70 ? 2 : 1) : (days > 900 ? 3 : 1);
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
