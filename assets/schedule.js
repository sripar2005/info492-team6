/* ClauseStream schedule engine, in the browser and in Node.
 *
 * Reads Primavera P6 XER, Microsoft Project XML (MSPDI), CSV and spreadsheet rows into one schedule
 * model (docs/demo4-spec.md section 1), runs the critical path method, checks schedule quality and
 * runs an AACE 52R-06 style prospective time impact analysis (TIA) of a fragnet.
 *
 * Day numbering (spec section 1): working day 0 is the first working day on or after schedule.start.
 * An activity with ES = 0 and duration 5 occupies working days 0-4; EF = 5 is an exclusive end and the
 * finish date shown is the date of working day 4. Durations, remaining durations and lags are in
 * working days of the one schedule calendar (calendar.workdays use 0 = Sunday ... 6 = Saturday).
 *
 * Pure functions, no dependencies. tools/schedule_test.js holds hand-computed tests.
 */
(function (root) {
  'use strict';

  var DAY_MS = 86400000;
  var DEFAULT_WORKDAYS = [1, 2, 3, 4, 5];
  var TYPES = { FS: 1, SS: 1, FF: 1, SF: 1 };

  // ---------- dates ----------
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function ms(d) { return Date.UTC(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10)); }
  function isoFromMs(t) { var d = new Date(t); return d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate()); }
  function addDays(d, n) { return isoFromMs(ms(d) + n * DAY_MS); }
  function dow(d) { return new Date(ms(d)).getUTCDay(); }
  function calDays(a, b) { return Math.round((ms(b) - ms(a)) / DAY_MS); }
  function validIso(s) { return typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s) && isoFromMs(ms(s)) === s; }
  var MONTHS = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
  function ymd(y, m, d) {
    y = +y; if (y < 100) y += 2000;
    var s = y + '-' + pad(+m) + '-' + pad(+d);
    return validIso(s) ? s : null;
  }
  function excelSerial(n) { return isoFromMs(Math.round((n - 25569) * DAY_MS)); }

  // Any date-like value -> { date: 'YYYY-MM-DD' | null, actual: bool }. "A" suffix is P6's actual-date mark.
  function readDate(v) {
    if (v === null || v === undefined || v === '') return { date: null, actual: false };
    if (Object.prototype.toString.call(v) === '[object Date]') {
      if (isNaN(v.getTime())) return { date: null, actual: false };
      return { date: v.getFullYear() + '-' + pad(v.getMonth() + 1) + '-' + pad(v.getDate()), actual: false };
    }
    if (typeof v === 'number') return { date: v > 1000 && v < 200000 ? excelSerial(v) : null, actual: false };
    var s = String(v).trim(), actual = false, m;
    if (/\s*\bA$/.test(s) && !/^\d{4}-\d{2}-\d{2}T/.test(s)) { actual = true; s = s.replace(/\s*\bA$/, ''); }
    s = s.replace(/\s*\*$/, '').replace(/^[A-Za-z]{3,9},?\s+(?=\d)/, '');
    if ((m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(s))) return { date: ymd(m[1], m[2], m[3]), actual: actual };
    if ((m = /^(\d{4})\/(\d{1,2})\/(\d{1,2})/.exec(s))) return { date: ymd(m[1], m[2], m[3]), actual: actual };
    if ((m = /^(\d{1,2})[\/.\-](\d{1,2})[\/.\-](\d{2,4})\b/.exec(s))) return { date: ymd(m[3], m[1], m[2]), actual: actual };
    if ((m = /^(\d{1,2})[\s\-]([A-Za-z]{3})[A-Za-z]*\.?[\s\-,]+(\d{2,4})\b/.exec(s)) && MONTHS[m[2].toLowerCase()]) return { date: ymd(m[3], MONTHS[m[2].toLowerCase()], m[1]), actual: actual };
    if ((m = /^([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{1,2}),?\s+(\d{2,4})\b/.exec(s)) && MONTHS[m[1].toLowerCase()]) return { date: ymd(m[3], MONTHS[m[1].toLowerCase()], m[2]), actual: actual };
    if (/^\d+(\.\d+)?$/.test(s)) return { date: +s > 1000 && +s < 200000 ? excelSerial(+s) : null, actual: actual };
    return { date: null, actual: actual };
  }
  function toDate(v) { return readDate(v).date; }

  // ---------- calendar ----------
  // Working-day index <-> date for one calendar, anchored at origin; indexes may be negative (actuals before start).
  function makeCalendar(cal, origin) {
    cal = cal || {};
    var wd = {}, hol = {}, any = false;
    (cal.workdays && cal.workdays.length ? cal.workdays : DEFAULT_WORKDAYS).forEach(function (d) { wd[((+d) % 7 + 7) % 7] = true; any = true; });
    if (!any) DEFAULT_WORKDAYS.forEach(function (d) { wd[d] = true; });
    (cal.holidays || []).forEach(function (h) { var d = toDate(h); if (d) hol[d] = true; });
    function isWork(d) { return !!wd[dow(d)] && !hol[d]; }
    var fwd = [], bwd = [], fNext = origin, bNext = addDays(origin, -1);
    function growF() { var g = 0; while (!isWork(fNext)) { fNext = addDays(fNext, 1); if (++g > 3700) throw new Error('Calendar has no working days'); } fwd.push(fNext); fNext = addDays(fNext, 1); }
    function growB() { var g = 0; while (!isWork(bNext)) { bNext = addDays(bNext, -1); if (++g > 3700) throw new Error('Calendar has no working days'); } bwd.push(bNext); bNext = addDays(bNext, -1); }
    function dateOf(i) {
      if (i >= 0) { while (fwd.length <= i) growF(); return fwd[i]; }
      var k = -i - 1; while (bwd.length <= k) growB(); return bwd[k];
    }
    // Index of the first working day on or after d.
    function index(d) {
      if (d >= origin) {
        while (!fwd.length || fwd[fwd.length - 1] < d) growF();
        var lo = 0, hi = fwd.length - 1;
        while (lo < hi) { var mid = (lo + hi) >> 1; if (fwd[mid] >= d) hi = mid; else lo = mid + 1; }
        return lo;
      }
      var best = 0;
      for (var k = 0; ; k++) { while (bwd.length <= k) growB(); if (bwd[k] >= d) best = -(k + 1); else break; }
      return best;
    }
    // Exclusive end index for "finishes on (or by) date d": one past the last working day on or before d.
    function finishIndex(d) { var i = index(d); return (dateOf(i) === d ? i : i - 1) + 1; }
    return { isWork: isWork, dateOf: dateOf, index: index, finishIndex: finishIndex, origin: origin };
  }

  // ---------- model helpers ----------
  function num(v) { if (v === null || v === undefined || v === '') return null; var n = +String(v).replace(/,/g, ''); return isFinite(n) ? n : null; }
  function r3(x) { return Math.round(x * 1000) / 1000; }
  function blankActivity(id, name) {
    return { id: id, name: name || '', duration: 0, wbs: '', actual_start: null, actual_finish: null, remaining: null, constraint: null, start: null, finish: null };
  }
  function schedule(o) {
    return { name: o.name || '', data_date: o.data_date || null, start: o.start || null,
      calendar: { workdays: (o.workdays || DEFAULT_WORKDAYS).slice(), holidays: (o.holidays || []).slice().sort() },
      activities: o.activities, relationships: o.relationships,
      source: { format: o.format, file: o.file || '', has_logic: !!o.has_logic, warnings: o.warnings || [] } };
  }
  function earliestDate(acts) {
    var best = null;
    acts.forEach(function (a) { [a.actual_start, a.start, a.constraint && a.constraint.date].forEach(function (d) { if (d && (!best || d < best)) best = d; }); });
    return best;
  }
  function relSort(acts, rels) {
    var pos = {}; acts.forEach(function (a, i) { pos[a.id] = i; });
    return rels.map(function (r, i) { return [r, i]; }).sort(function (x, y) {
      var a = (pos[x[0].succ] === undefined ? 1e9 : pos[x[0].succ]) - (pos[y[0].succ] === undefined ? 1e9 : pos[y[0].succ]);
      return a || x[1] - y[1];
    }).map(function (x) { return x[0]; });
  }

  // ---------- XER ----------
  function readXERTables(text) {
    var tables = {}, cur = null;
    String(text).replace(/^﻿/, '').split(/\r?\n/).forEach(function (line) {
      if (!line) return;
      var cells = line.split('\t'), tag = cells[0];
      if (tag === '%T') { cur = { fields: [], rows: [] }; tables[(cells[1] || '').trim()] = cur; }
      else if (tag === '%F' && cur) cur.fields = cells.slice(1).map(function (f) { return f.trim(); });
      else if (tag === '%R' && cur) { var row = {}; cur.fields.forEach(function (f, i) { row[f] = cells[i + 1] === undefined ? '' : cells[i + 1]; }); cur.rows.push(row); }
      else if (tag === '%E') cur = null;
    });
    return tables;
  }
  // P6 clndr_data: DaysOfWeek (1 = Sunday .. 7 = Saturday) with work intervals, and Exceptions keyed by Excel serial date.
  function parseP6CalendarData(data) {
    if (!data || data.indexOf('DaysOfWeek') < 0) return null;
    var s = String(data), iDays = s.indexOf('DaysOfWeek'), iExc = s.indexOf('Exceptions'), iView = s.indexOf('VIEW');
    var endDays = Math.min.apply(null, [iExc, iView, s.length].filter(function (x) { return x > iDays; }));
    var days = s.slice(iDays, endDays), marks = [], re = /\(0\|\|([1-7])\(\)/g, m;
    while ((m = re.exec(days))) marks.push({ d: +m[1], at: m.index });
    if (!marks.length) return null;
    var workdays = [];
    marks.forEach(function (mk, i) { var seg = days.slice(mk.at + 6, i + 1 < marks.length ? marks[i + 1].at : days.length); if (/s\|\d/.test(seg)) workdays.push(mk.d - 1); });
    var holidays = [];
    if (iExc >= 0) {
      var exc = s.slice(iExc), er = /\(0\|\|\d+\(d\|(\d+)\)\(/g, em, ex = [];
      while ((em = er.exec(exc))) ex.push({ serial: +em[1], at: em.index });
      ex.forEach(function (e, i) { var seg = exc.slice(e.at, i + 1 < ex.length ? ex[i + 1].at : exc.length); if (!/s\|\d/.test(seg)) holidays.push(excelSerial(e.serial)); });
    }
    return { workdays: workdays.sort(), holidays: holidays.sort() };
  }

  var P6_CSTR = { CS_MSOA: 'SNET', CS_MEOB: 'FNLT', CS_MSO: 'MSO', CS_MANDSTART: 'MSO', CS_MEO: 'MFO', CS_MANDFIN: 'MFO' };
  var P6_REL = { PR_FS: 'FS', PR_SS: 'SS', PR_FF: 'FF', PR_SF: 'SF' };

  function parseXER(text, opts) {
    opts = opts || {};
    var t = readXERTables(text), warnings = [];
    var rows = function (n) { return t[n] ? t[n].rows : []; };
    var tasks = rows('TASK');
    // Several projects in one file: keep the one with the most activities.
    var projects = rows('PROJECT'), count = {};
    tasks.forEach(function (r) { count[r.proj_id] = (count[r.proj_id] || 0) + 1; });
    var proj = projects.slice().sort(function (a, b) { return (count[b.proj_id] || 0) - (count[a.proj_id] || 0); })[0] || {};
    if (projects.length > 1) warnings.push('XER holds ' + projects.length + ' projects; read ' + (proj.proj_short_name || proj.proj_id) + ' only.');
    if (proj.proj_id) tasks = tasks.filter(function (r) { return !r.proj_id || r.proj_id === proj.proj_id; });

    var wbs = {}; rows('PROJWBS').forEach(function (w) { wbs[w.wbs_id] = w.wbs_name || w.wbs_short_name || ''; });
    // Calendar: the one most activities use (else the project default).
    var cals = {}; rows('CALENDAR').forEach(function (c) { cals[c.clndr_id] = c; });
    var use = {}; tasks.forEach(function (r) { if (r.clndr_id) use[r.clndr_id] = (use[r.clndr_id] || 0) + 1; });
    var calIds = Object.keys(use).sort(function (a, b) { return use[b] - use[a]; });
    var calRow = cals[calIds[0]] || cals[proj.clndr_id] || null;
    if (calIds.length > 1) warnings.push('Activities use ' + calIds.length + ' calendars; all are scheduled on "' + ((calRow && calRow.clndr_name) || calIds[0]) + '".');
    var cal = calRow ? parseP6CalendarData(calRow.clndr_data) : null;
    if (!cal) warnings.push('Calendar not readable from the XER; using Monday-Friday with no holidays.');
    var hpd = calRow && num(calRow.day_hr_cnt) ? num(calRow.day_hr_cnt) : 8;

    var byTaskId = {}, acts = [], skipped = {};
    tasks.forEach(function (r) {
      var type = r.task_type || '';
      if (type === 'TT_WBS' || type === 'TT_LOE') { skipped[r.task_id] = true; warnings.push('Skipped ' + (type === 'TT_LOE' ? 'level-of-effort' : 'WBS summary') + ' activity ' + r.task_code + '.'); return; }
      var a = blankActivity(r.task_code || r.task_id, r.task_name);
      var milestone = type === 'TT_Mile' || type === 'TT_FinMile';
      a.duration = milestone ? 0 : r3((num(r.target_drtn_hr_cnt) || 0) / hpd);
      a.wbs = wbs[r.wbs_id] || '';
      a.actual_start = toDate(r.act_start_date);
      a.actual_finish = toDate(r.act_end_date);
      if (a.actual_start && !a.actual_finish && !milestone) a.remaining = r3((num(r.remain_drtn_hr_cnt) || 0) / hpd);
      var ct = P6_CSTR[r.cstr_type], cd = toDate(r.cstr_date);
      if (ct && cd) a.constraint = { type: ct, date: cd };
      else if (r.cstr_type && r.cstr_type !== 'CS_ALAP') warnings.push('Constraint ' + r.cstr_type + ' on ' + a.id + ' is not modeled.');
      a.start = toDate(r.act_start_date || r.early_start_date || r.target_start_date);
      a.finish = toDate(r.act_end_date || r.early_end_date || r.target_end_date);
      byTaskId[r.task_id] = a.id; acts.push(a);
    });
    var rels = [];
    rows('TASKPRED').forEach(function (r) {
      if (skipped[r.task_id] || skipped[r.pred_task_id]) return;
      var succ = byTaskId[r.task_id], pred = byTaskId[r.pred_task_id];
      if (!succ || !pred) { warnings.push('Relationship ' + r.pred_task_id + ' -> ' + r.task_id + ' points outside this project.'); if (!succ || !pred) return; }
      rels.push({ pred: pred, succ: succ, type: P6_REL[r.pred_type] || 'FS', lag: r3((num(r.lag_hr_cnt) || 0) / hpd) });
    });
    return schedule({ name: opts.name || proj.proj_short_name || '', format: 'xer', file: opts.file,
      data_date: toDate(proj.last_recalc_date) || toDate(proj.next_data_date) || null,
      start: toDate(proj.plan_start_date) || earliestDate(acts),
      workdays: cal ? cal.workdays : DEFAULT_WORKDAYS, holidays: cal ? cal.holidays : [],
      activities: acts, relationships: relSort(acts, rels), has_logic: rels.length > 0, warnings: warnings });
  }

  // ---------- tiny XML reader (no DOMParser) ----------
  function decodeXML(s) {
    return s.replace(/&(#x[0-9a-fA-F]+|#\d+|lt|gt|amp|quot|apos);/g, function (_, e) {
      if (e[0] === '#') return String.fromCharCode(e[1] === 'x' ? parseInt(e.slice(2), 16) : +e.slice(1));
      return { lt: '<', gt: '>', amp: '&', quot: '"', apos: "'" }[e];
    });
  }
  function parseXML(text) {
    var top = { name: '#root', attrs: {}, children: [], text: '' }, stack = [top], m;
    var re = /<!\[CDATA\[([\s\S]*?)\]\]>|<!--[\s\S]*?-->|<\?[\s\S]*?\?>|<!DOCTYPE[^>]*>|<\/\s*([^\s>]+)\s*>|<([A-Za-z_][^\s\/>]*)((?:[^>"']|"[^"]*"|'[^']*')*?)(\/?)>|([^<]+)/g;
    var strip = function (n) { return n.replace(/^.*:/, ''); };
    while ((m = re.exec(String(text)))) {
      var cur = stack[stack.length - 1];
      if (m[1] !== undefined) cur.text += m[1];
      else if (m[2]) {
        var nm = strip(m[2]);
        for (var i = stack.length - 1; i > 0; i--) if (stack[i].name === nm) { stack.length = i; break; }
      } else if (m[3]) {
        var node = { name: strip(m[3]), attrs: {}, children: [], text: '' }, am, ar = /([^\s=]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g;
        while ((am = ar.exec(m[4]))) node.attrs[strip(am[1])] = decodeXML(am[2] !== undefined ? am[2] : am[3]);
        cur.children.push(node);
        if (!m[5]) stack.push(node);
      } else if (m[6] !== undefined) cur.text += decodeXML(m[6]);
    }
    return top;
  }
  function kid(n, name) { if (!n) return null; for (var i = 0; i < n.children.length; i++) if (n.children[i].name === name) return n.children[i]; return null; }
  function kids(n, name) { return n ? n.children.filter(function (c) { return c.name === name; }) : []; }
  function txt(n, name) { var k = kid(n, name); return k ? k.text.trim() : ''; }

  // ISO 8601 duration (PT40H0M0S) -> hours. A "D" part counts as working days of hoursPerDay.
  function isoHours(s, hpd) {
    var m = /^(-)?P(?:(\d+(?:\.\d+)?)Y)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)W)?(?:(\d+(?:\.\d+)?)D)?(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?$/.exec(String(s || '').trim());
    if (!m) return null;
    var h = (+m[4] || 0) * 5 * hpd + (+m[5] || 0) * hpd + (+m[6] || 0) + (+m[7] || 0) / 60 + (+m[8] || 0) / 3600;
    return m[1] ? -h : h;
  }
  var MSP_REL = { 0: 'FF', 1: 'FS', 2: 'SF', 3: 'SS' };
  var MSP_CSTR = { 2: 'MSO', 3: 'MFO', 4: 'SNET', 7: 'FNLT' };
  var MSP_CSTR_NAME = { 1: 'ALAP', 5: 'SNLT', 6: 'FNET' };
  var TEXT1 = '188743731';

  function parseMSPDI(xmlText, opts) {
    opts = opts || {};
    var doc = parseXML(xmlText), proj = kid(doc, 'Project'), warnings = [];
    if (!proj) throw new Error('Not a Microsoft Project XML file (no <Project> element).');
    var mpd = num(txt(proj, 'MinutesPerDay')) || 480, hpd = mpd / 60;
    // Calendar: the project calendar, else the first base calendar.
    var cals = kids(kid(proj, 'Calendars'), 'Calendar'), cuid = txt(proj, 'CalendarUID');
    var calNode = cals.filter(function (c) { return txt(c, 'UID') === cuid; })[0] || cals.filter(function (c) { return txt(c, 'IsBaseCalendar') === '1'; })[0] || cals[0];
    var workdays = [], holidays = [], calOk = false;
    function addRange(tp) {
      var a = toDate(txt(tp, 'FromDate')), b = toDate(txt(tp, 'ToDate'));
      if (!a) return; if (!b || b < a) b = a;
      for (var d = a, g = 0; d <= b && g < 3700; d = addDays(d, 1), g++) holidays.push(d);
    }
    if (calNode) {
      kids(kid(calNode, 'WeekDays'), 'WeekDay').forEach(function (w) {
        var t = +txt(w, 'DayType'), working = txt(w, 'DayWorking') === '1';
        if (t >= 1 && t <= 7) { calOk = true; if (working) workdays.push(t - 1); }
        else if (t === 0 && !working) addRange(kid(w, 'TimePeriod'));
      });
      kids(kid(calNode, 'Exceptions'), 'Exception').forEach(function (e) { if (txt(e, 'DayWorking') !== '1') addRange(kid(e, 'TimePeriod')); });
    }
    if (!calOk || !workdays.length) { workdays = DEFAULT_WORKDAYS.slice(); warnings.push('Calendar not readable from the XML; using Monday-Friday.'); }
    // Activity ID: Text1 or a custom field aliased like "Activity ID"; else the task's ID (row number).
    var idFields = [TEXT1];
    kids(kid(proj, 'ExtendedAttributes'), 'ExtendedAttribute').forEach(function (x) { if (/activity\s*id|task\s*code|act(ivity)?\s*code/i.test(txt(x, 'Alias'))) idFields.unshift(txt(x, 'FieldID')); });
    var tasks = kids(kid(proj, 'Tasks'), 'Task'), uidToId = {}, acts = [], linkSrc = [], summaryAt = [], skipped = {}, usedText = false;
    tasks.forEach(function (t) {
      var uid = txt(t, 'UID'), level = num(txt(t, 'OutlineLevel')), name = txt(t, 'Name');
      if (txt(t, 'IsNull') === '1' || uid === '0' || (!name && !txt(t, 'Duration'))) { skipped[uid] = true; return; }
      if (txt(t, 'Summary') === '1') { if (level !== null) { summaryAt[level] = name; summaryAt.length = level + 1; } skipped[uid] = true; return; }
      var code = '';
      kids(t, 'ExtendedAttribute').forEach(function (x) { var f = txt(x, 'FieldID'), v = txt(x, 'Value'); if (v && idFields.indexOf(f) >= 0 && (!code || f !== TEXT1)) code = v; });
      if (code) usedText = true;
      var a = blankActivity(code || txt(t, 'ID') || uid, name);
      var milestone = txt(t, 'Milestone') === '1';
      a.duration = milestone ? 0 : r3((isoHours(txt(t, 'Duration'), hpd) || 0) / hpd);
      var parent = ''; if (level !== null) for (var l = level - 1; l >= 1; l--) if (summaryAt[l]) { parent = summaryAt[l]; break; }
      a.wbs = parent;
      a.actual_start = toDate(txt(t, 'ActualStart'));
      a.actual_finish = toDate(txt(t, 'ActualFinish'));
      if (a.actual_start && !a.actual_finish && !milestone) a.remaining = r3((isoHours(txt(t, 'RemainingDuration'), hpd) || 0) / hpd);
      var ct = num(txt(t, 'ConstraintType')), cd = toDate(txt(t, 'ConstraintDate'));
      if (MSP_CSTR[ct] && cd) a.constraint = { type: MSP_CSTR[ct], date: cd };
      else if (MSP_CSTR_NAME[ct]) warnings.push('Constraint ' + MSP_CSTR_NAME[ct] + ' on ' + a.id + ' is not modeled.');
      a.start = toDate(txt(t, 'Start')); a.finish = toDate(txt(t, 'Finish'));
      uidToId[uid] = a.id; acts.push(a);
      kids(t, 'PredecessorLink').forEach(function (p) { linkSrc.push({ succ: a.id, p: p }); });
    });
    if (!usedText && acts.length) warnings.push('No activity ID field (Text1) found; using Microsoft Project row IDs.');
    var rels = [];
    linkSrc.forEach(function (x) {
      var pu = txt(x.p, 'PredecessorUID'), pred = uidToId[pu];
      if (!pred) { warnings.push('Link from ' + (skipped[pu] ? 'summary/blank task UID ' : 'unknown UID ') + pu + ' to ' + x.succ + ' dropped.'); return; }
      var fmt = num(txt(x.p, 'LagFormat')), lag = (num(txt(x.p, 'LinkLag')) || 0) / (mpd * 10);
      if (fmt === 19 || fmt === 20) { warnings.push('Percent lag on ' + pred + ' -> ' + x.succ + ' read as 0.'); lag = 0; }
      var tp = txt(x.p, 'Type'); rels.push({ pred: pred, succ: x.succ, type: MSP_REL[tp === '' ? 1 : +tp] || 'FS', lag: r3(lag) });
    });
    return schedule({ name: opts.name || txt(proj, 'Title') || txt(proj, 'Name'), format: 'mspdi', file: opts.file,
      data_date: toDate(txt(proj, 'StatusDate')) || null, start: toDate(txt(proj, 'StartDate')) || earliestDate(acts),
      workdays: workdays.sort(), holidays: holidays.filter(function (d, i, a) { return a.indexOf(d) === i; }),
      activities: acts, relationships: rels, has_logic: rels.length > 0, warnings: warnings });
  }

  // ---------- CSV / spreadsheet rows ----------
  function splitCSV(text) {
    text = String(text).replace(/^﻿/, '');
    var first = text.split(/\r?\n/)[0] || '', counts = { ',': 0, '\t': 0, ';': 0 }, q = false;
    for (var i = 0; i < first.length; i++) { var ch = first[i]; if (ch === '"') q = !q; else if (!q && counts[ch] !== undefined) counts[ch]++; }
    var delim = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; })[0];
    if (!counts[delim]) delim = ',';
    var rows = [], row = [], field = '', inQ = false;
    for (var j = 0; j < text.length; j++) {
      var c = text[j];
      if (inQ) {
        if (c === '"') { if (text[j + 1] === '"') { field += '"'; j++; } else inQ = false; }
        else field += c;
      } else if (c === '"') inQ = true;
      else if (c === delim) { row.push(field); field = ''; }
      else if (c === '\n' || c === '\r') { if (c === '\r' && text[j + 1] === '\n') j++; row.push(field); rows.push(row); row = []; field = ''; }
      else field += c;
    }
    if (field !== '' || row.length) { row.push(field); rows.push(row); }
    return rows.filter(function (r) { return r.some(function (x) { return String(x).trim() !== ''; }); });
  }

  var ALIASES = {
    id: ['id', 'activityid', 'taskid', 'actid', 'activitycode', 'taskcode', 'uid', 'uniqueid', 'code'],
    name: ['name', 'activityname', 'taskname', 'description', 'activitydescription', 'task', 'activity'],
    duration: ['duration', 'originalduration', 'dur', 'origdur', 'od', 'plannedduration', 'durationdays', 'atcompletionduration'],
    remaining: ['remainingduration', 'remaining', 'remdur', 'rd'],
    start: ['start', 'startdate', 'plannedstart', 'earlystart', 'es', 'begin'],
    finish: ['finish', 'finishdate', 'end', 'enddate', 'plannedfinish', 'earlyfinish', 'ef'],
    actual_start: ['actualstart', 'actualstartdate'],
    actual_finish: ['actualfinish', 'actualfinishdate'],
    predecessors: ['predecessors', 'predecessor', 'preds', 'pred', 'predecessorids', 'predecessorlist'],
    wbs: ['wbs', 'wbsname', 'wbspath', 'wbscode', 'phase', 'area'],
    constraint: ['constraint', 'constrainttype', 'primaryconstraint'],
    constraint_date: ['constraintdate', 'primaryconstraintdate']
  };
  function normHeader(h) { return String(h === undefined || h === null ? '' : h).replace(/\([^)]*\)/g, '').toLowerCase().replace(/[^a-z0-9]/g, ''); }
  function mapHeaders(headers) {
    var map = {};
    headers.forEach(function (h, i) {
      var n = normHeader(h);
      Object.keys(ALIASES).forEach(function (k) { if (map[k] === undefined && ALIASES[k].indexOf(n) >= 0) map[k] = i; });
    });
    return map;
  }
  // "5", "5d", "5 days", "40h", "2w", 0 -> working days (null if unreadable).
  function readDuration(v) {
    if (v === null || v === undefined || v === '') return null;
    if (typeof v === 'number') return v;
    var m = /^\s*(-?\d+(?:\.\d+)?)\s*(d|days?|wd|edays?|h|hrs?|hours?|w|wks?|weeks?|mo|mons?|months?)?\??\s*$/i.exec(String(v).replace(/,/g, ''));
    if (!m) return null;
    var n = +m[1], u = (m[2] || 'd').toLowerCase();
    if (u[0] === 'h') return n / 8;
    if (u[0] === 'w') return n * 5;
    if (u.slice(0, 2) === 'mo') return n * 20;
    return n;
  }
  var CSTR_WORDS = [[/^(snet|start\s*on\s*or\s*after|start\s*no\s*earlier\s*than)$/i, 'SNET'], [/^(fnlt|finish\s*on\s*or\s*before|finish\s*no\s*later\s*than)$/i, 'FNLT'],
    [/^(mso|must\s*start\s*on|mandatory\s*start|start\s*on)$/i, 'MSO'], [/^(mfo|must\s*finish\s*on|mandatory\s*finish|finish\s*on)$/i, 'MFO']];
  // "A1010FS+2, A1020SS, A1030" or "3FS+2 days; 5SS-1d" -> [{pred, type, lag}]
  function parsePredecessors(s) {
    var out = [];
    String(s || '').split(/[,;\n]+/).forEach(function (tok) {
      tok = tok.trim(); if (!tok) return;
      var m = /^(.*?)\s*[:\s]?(FS|SS|FF|SF)?\s*(?:([+\-])\s*(\d+(?:\.\d+)?)\s*(d|days?|wd|edays?|h|hrs?|hours?|w|wks?|weeks?)?)?\s*$/i.exec(tok);
      if (!m || !m[1]) return;
      var lag = m[4] ? (readDuration(m[4] + (m[5] || 'd')) || 0) * (m[3] === '-' ? -1 : 1) : 0;
      out.push({ pred: m[1].trim(), type: (m[2] || 'FS').toUpperCase(), lag: r3(lag) });
    });
    return out;
  }
  function parseRows(rows, opts) {
    opts = opts || {};
    rows = rows || [];
    var warnings = [], headers, body;
    if (rows.length && !Array.isArray(rows[0]) && typeof rows[0] === 'object') {
      headers = []; rows.forEach(function (r) { Object.keys(r).forEach(function (k) { if (headers.indexOf(k) < 0) headers.push(k); }); });
      body = rows.map(function (r) { return headers.map(function (h) { return r[h]; }); });
    } else {
      // Header row: first of the top 10 rows naming an id or name column plus one more known column.
      var hi = 0;
      for (var i = 0; i < Math.min(rows.length, 10); i++) { var mp = mapHeaders(rows[i]); if ((mp.id !== undefined || mp.name !== undefined) && Object.keys(mp).length >= 2) { hi = i; break; } }
      headers = rows[hi] || []; body = rows.slice(hi + 1);
    }
    var map = mapHeaders(headers), acts = [], rels = [], seen = {}, curWbs = '';
    if (map.id === undefined && map.name === undefined) throw new Error('No activity id or name column found.');
    var cell = function (r, k) { return map[k] === undefined ? undefined : r[map[k]]; };
    var str = function (v) { return v === undefined || v === null ? '' : String(v).trim(); };
    var cal = makeCalendar(opts.calendar, '2000-01-03');
    body.forEach(function (r, n) {
      var id = str(cell(r, 'id')), name = str(cell(r, 'name')), dur = readDuration(cell(r, 'duration'));
      var s = readDate(cell(r, 'start')), f = readDate(cell(r, 'finish'));
      if (!id && !name) return;
      if (!id) {
        // A banded WBS row (name only, no dates or duration) sets the WBS for the rows under it.
        if (dur === null && !s.date && !f.date) { curWbs = name; return; }
        id = 'ROW' + (n + 1); warnings.push('Row ' + (n + 1) + ' has no activity id; using ' + id + '.');
      }
      if (seen[id]) { warnings.push('Duplicate activity id ' + id + ' skipped.'); return; }
      seen[id] = true;
      var a = blankActivity(id, name);
      if (dur === null && s.date && f.date) { dur = Math.max(0, cal.finishIndex(f.date) - cal.index(s.date)); warnings.push('Duration of ' + id + ' computed from its dates.'); }
      if (dur === null) { dur = 0; warnings.push('No duration for ' + id + '; read as 0.'); }
      a.duration = r3(dur);
      a.wbs = map.wbs !== undefined ? str(cell(r, 'wbs')) : curWbs;
      a.start = s.date; a.finish = f.date;
      var as = readDate(cell(r, 'actual_start')).date || (s.actual ? s.date : null);
      var af = readDate(cell(r, 'actual_finish')).date || (f.actual ? f.date : null);
      a.actual_start = as; a.actual_finish = af;
      if (as && !af && dur > 0) { var rem = readDuration(cell(r, 'remaining')); a.remaining = rem === null ? null : r3(rem); }
      var ct = str(cell(r, 'constraint')), cd = toDate(cell(r, 'constraint_date'));
      if (ct) {
        var hit = CSTR_WORDS.filter(function (w) { return w[0].test(ct); })[0];
        if (hit && cd) a.constraint = { type: hit[1], date: cd }; else warnings.push('Constraint "' + ct + '" on ' + id + ' not read.');
      }
      acts.push(a);
      if (map.predecessors !== undefined) parsePredecessors(cell(r, 'predecessors')).forEach(function (p) { rels.push({ pred: p.pred, succ: id, type: p.type, lag: p.lag }); });
    });
    var hasLogic = map.predecessors !== undefined && rels.length > 0;
    if (map.predecessors === undefined) warnings.push('No predecessors column: logic (and the critical path) cannot be verified.');
    var minStart = null; acts.forEach(function (a) { var d = a.actual_start || a.start; if (d && (!minStart || d < minStart)) minStart = d; });
    return schedule({ name: opts.name || '', format: opts.format || 'csv', file: opts.file, data_date: opts.data_date || null,
      start: opts.start || minStart || earliestDate(acts),
      workdays: (opts.calendar && opts.calendar.workdays) || DEFAULT_WORKDAYS, holidays: (opts.calendar && opts.calendar.holidays) || [],
      activities: acts, relationships: rels, has_logic: hasLogic, warnings: warnings });
  }
  function parseCSV(text, opts) { return parseRows(splitCSV(text), opts); }

  // ---------- graph helpers ----------
  // Strongly connected components (iterative Tarjan); returns arrays of ids in cycles (size > 1 or self-loop).
  function cycles(ids, edges) {
    var adj = {}; ids.forEach(function (id) { adj[id] = []; });
    var self = {};
    edges.forEach(function (e) { if (adj[e.pred] && adj[e.succ]) { adj[e.pred].push(e.succ); if (e.pred === e.succ) self[e.pred] = true; } });
    var index = {}, low = {}, onStack = {}, st = [], out = [], counter = 0;
    ids.forEach(function (start) {
      if (index[start] !== undefined) return;
      var work = [[start, 0]]; index[start] = low[start] = counter++; st.push(start); onStack[start] = true;
      while (work.length) {
        var top = work[work.length - 1], v = top[0];
        if (top[1] < adj[v].length) {
          var w = adj[v][top[1]++];
          if (index[w] === undefined) { index[w] = low[w] = counter++; st.push(w); onStack[w] = true; work.push([w, 0]); }
          else if (onStack[w]) low[v] = Math.min(low[v], index[w]);
        } else {
          work.pop();
          if (work.length) { var u = work[work.length - 1][0]; low[u] = Math.min(low[u], low[v]); }
          if (low[v] === index[v]) {
            var comp = [], x; do { x = st.pop(); onStack[x] = false; comp.push(x); } while (x !== v);
            if (comp.length > 1 || self[v]) out.push(comp.reverse());
          }
        }
      }
    });
    return out;
  }
  // Edges that close a cycle (back edges of a depth-first search in list order).
  function backEdges(ids, edges) {
    var out = {}, adj = {}, color = {};
    ids.forEach(function (id) { adj[id] = []; });
    edges.forEach(function (e, i) { if (adj[e.pred]) adj[e.pred].push(i); });
    ids.forEach(function (s) {
      if (color[s]) return;
      var work = [[s, 0]]; color[s] = 1;
      while (work.length) {
        var top = work[work.length - 1], v = top[0];
        if (top[1] < adj[v].length) {
          var ei = adj[v][top[1]++], w = edges[ei].succ;
          if (color[w] === 1) out[ei] = true;
          else if (!color[w]) { color[w] = 1; work.push([w, 0]); }
        } else { color[v] = 2; work.pop(); }
      }
    });
    return out;
  }
  // Kahn topological order, ties broken by list position.
  function topoOrder(ids, edges) {
    var pos = {}, indeg = {}, adj = {};
    ids.forEach(function (id, i) { pos[id] = i; indeg[id] = 0; adj[id] = []; });
    edges.forEach(function (e) { adj[e.pred].push(e.succ); indeg[e.succ]++; });
    var heap = [], out = [];
    function push(x) { heap.push(x); var i = heap.length - 1; while (i > 0) { var p = (i - 1) >> 1; if (pos[heap[p]] <= pos[heap[i]]) break; var t = heap[p]; heap[p] = heap[i]; heap[i] = t; i = p; } }
    function pop() { var r = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; var i = 0; for (;;) { var l = 2 * i + 1, rr = l + 1, m = i; if (l < heap.length && pos[heap[l]] < pos[heap[m]]) m = l; if (rr < heap.length && pos[heap[rr]] < pos[heap[m]]) m = rr; if (m === i) break; var t = heap[m]; heap[m] = heap[i]; heap[i] = t; i = m; } } return r; }
    ids.forEach(function (id) { if (!indeg[id]) push(id); });
    while (heap.length) { var v = pop(); out.push(v); adj[v].forEach(function (w) { if (!--indeg[w]) push(w); }); }
    return out;
  }

  // ---------- CPM ----------
  function cpm(sched) {
    var warnings = [], src = sched.source || {}, hasLogic = src.has_logic !== false;
    var acts = [], byId = {};
    (sched.activities || []).forEach(function (a) {
      var id = String(a.id);
      if (byId[id]) { warnings.push('Duplicate activity id ' + id + '; the second one is ignored.'); return; }
      var d = num(a.duration) || 0;
      if (d < 0) { warnings.push('Negative duration on ' + id + ' read as 0.'); d = 0; }
      if (d !== Math.ceil(d)) warnings.push('Duration ' + d + ' on ' + id + ' rounded up to whole working days.');
      var x = { a: a, id: id, dur: Math.ceil(d), pos: acts.length, inc: [], out: [] };
      byId[id] = x; acts.push(x);
    });
    var rels = [];
    (sched.relationships || []).forEach(function (r) {
      var p = String(r.pred), s = String(r.succ);
      if (!byId[p] || !byId[s]) { warnings.push('Relationship ' + p + ' -> ' + s + ' points to a missing activity and is ignored.'); return; }
      var type = String(r.type || 'FS').toUpperCase();
      if (!TYPES[type]) { warnings.push('Unknown relationship type ' + r.type + ' on ' + p + ' -> ' + s + '; read as FS.'); type = 'FS'; }
      var lag = num(r.lag) || 0;
      if (lag !== Math.round(lag)) { warnings.push('Lag ' + lag + ' on ' + p + ' -> ' + s + ' rounded to whole working days.'); lag = Math.round(lag); }
      rels.push({ pred: p, succ: s, type: type, lag: lag });
    });
    var ids = acts.map(function (x) { return x.id; });
    var back = backEdges(ids, rels);
    if (Object.keys(back).length) {
      cycles(ids, rels).forEach(function (c) { warnings.push('Logic loop (cycle) among ' + c.join(', ') + '; the link closing the loop is ignored.'); });
      rels = rels.filter(function (r, i) { return !back[i]; });
    }
    rels.forEach(function (r) { byId[r.succ].inc.push(r); byId[r.pred].out.push(r); });
    var order = topoOrder(ids, rels).map(function (id) { return byId[id]; });
    order.forEach(function (x, i) { x.topo = i; });

    var origin = toDate(sched.start) || toDate(sched.data_date) || earliestDate(sched.activities || []);
    if (!origin) { origin = '2000-01-03'; warnings.push('Schedule has no start date; dates are counted from ' + origin + '.'); }
    var cal = makeCalendar(sched.calendar, origin);
    var dataDate = toDate(sched.data_date), dd = dataDate ? cal.index(dataDate) : null;
    var floor = Math.max(0, dd === null ? 0 : dd);
    if (!hasLogic) warnings.push('Schedule has no logic (relationships were not read): dates use each activity\'s own start; the critical path is not verifiable.');

    function req(r, p, x) { // earliest ES of x allowed by relationship r from p
      var dx = x.effDur;
      switch (r.type) {
        case 'SS': return p.es + r.lag;
        case 'FF': return p.ef + r.lag - dx;
        case 'SF': return p.es + r.lag - dx;
        default: return p.ef + r.lag;
      }
    }
    // Forward pass.
    order.forEach(function (x) {
      var a = x.a, as = toDate(a.actual_start), af = toDate(a.actual_finish), c = a.constraint;
      if (af) {
        x.status = 'complete';
        x.ef = cal.finishIndex(af);
        x.es = as ? cal.index(as) : x.ef - x.dur;
        if (x.es > x.ef) x.es = x.ef;
        x.effDur = x.ef - x.es;
        if (dataDate && af >= dataDate) warnings.push('Activity ' + x.id + ' has an actual finish on or after the data date.');
        x.reason = 'actual';
        return;
      }
      if (as) {
        x.status = 'in_progress';
        x.es = cal.index(as);
        var rem = num(a.remaining);
        var rs = dd !== null ? Math.max(dd, x.es) : x.es + Math.max(0, x.dur - (rem === null ? x.dur : rem));
        if (rem === null) { rem = Math.max(0, x.dur - (rs - x.es)); warnings.push('No remaining duration for in-progress ' + x.id + '; estimated as ' + rem + ' days.'); }
        if (dd === null) warnings.push('In-progress ' + x.id + ' but the schedule has no data date.');
        x.rs = rs; x.effDur = Math.ceil(rem); x.ef = rs + x.effDur;
        x.reason = 'actual';
        return;
      }
      x.status = 'not_started'; x.effDur = x.dur;
      var es = floor, reason = dd !== null && dd > 0 ? 'data_date' : 'start';
      if (!hasLogic && toDate(a.start)) { var ps = cal.index(toDate(a.start)); if (ps > es) { es = ps; reason = 'planned_start'; } }
      x.inc.forEach(function (r) { var v = req(r, byId[r.pred], x); if (v >= es) { es = v; reason = 'logic'; } });
      if (c && toDate(c.date)) {
        var ci = cal.index(toDate(c.date));
        if (c.type === 'SNET' && ci > es) { es = ci; reason = 'constraint'; }
        if (c.type === 'MSO') {
          if (es > ci) warnings.push('Mandatory start (MSO ' + c.date + ') on ' + x.id + ' is earlier than its logic allows (' + cal.dateOf(es) + '); constraint wins.');
          es = Math.max(ci, floor); reason = 'constraint';
        }
      }
      x.es = es; x.ef = es + x.effDur; x.reason = reason;
    });
    var pf = acts.length ? Math.max.apply(null, acts.map(function (x) { return x.ef; })) : 0;
    // Backward pass.
    for (var i = order.length - 1; i >= 0; i--) {
      var x = order[i], a = x.a, c = a.constraint;
      if (x.status === 'complete') { x.ls = x.es; x.lf = x.ef; continue; }
      var lf = pf, d = x.effDur;
      x.out.forEach(function (r) {
        var q = byId[r.succ]; if (q.status === 'complete') return;
        var qls = q.lf - q.effDur, v;
        switch (r.type) {
          case 'SS': v = qls - r.lag + d; break;
          case 'FF': v = q.lf - r.lag; break;
          case 'SF': v = q.lf - r.lag + d; break;
          default: v = qls - r.lag;
        }
        if (v < lf) lf = v;
      });
      if (c && toDate(c.date) && (c.type === 'FNLT' || c.type === 'MFO')) {
        var fi = cal.finishIndex(toDate(c.date));
        if (x.ef > fi) warnings.push((c.type === 'FNLT' ? 'Finish-no-later-than' : 'Mandatory finish') + ' ' + c.date + ' on ' + x.id + ' is violated: early finish is ' + (x.effDur ? cal.dateOf(x.ef - 1) : cal.dateOf(x.ef)) + '.');
        if (c.type === 'FNLT') lf = Math.min(lf, fi); else lf = fi;
      }
      x.lf = lf; x.ls = lf - d;
    }
    function shown(x, early) {
      var s = early ? x.es : x.ls, f = early ? x.ef : x.lf;
      if (x.dur === 0 && x.status !== 'in_progress') {
        // Milestones driven by FS/FF links are finish milestones: they fall on their predecessor's last working day.
        var fin = x.inc.some(function (r) { return r.type === 'FS' || r.type === 'FF'; }) && (x.status !== 'complete');
        var d = fin && f > 0 ? cal.dateOf(f - 1) : cal.dateOf(s);
        if (x.status === 'complete') d = toDate(x.a.actual_finish);
        return [d, d];
      }
      return [cal.dateOf(s), f > s ? cal.dateOf(f - 1) : cal.dateOf(s)];
    }
    var out = acts.map(function (x) {
      var tf = x.status === 'complete' ? null : x.lf - x.ef, e = shown(x, true), l = shown(x, false);
      var startDate = x.status === 'complete' || x.status === 'in_progress' ? (toDate(x.a.actual_start) || e[0]) : e[0];
      var finDate = x.status === 'complete' ? toDate(x.a.actual_finish) : e[1];
      x.tf = tf; x.critical = hasLogic && tf !== null && tf <= 0;
      return { id: x.id, name: x.a.name || '', es: x.es, ef: x.ef, ls: x.ls, lf: x.lf, total_float: tf, critical: x.critical,
        start: startDate, finish: finDate, late_start: x.status === 'complete' ? null : l[0], late_finish: x.status === 'complete' ? null : l[1],
        status: x.status, duration: x.dur, remaining: x.status === 'in_progress' ? x.effDur : null, wbs: x.a.wbs || '' };
    });
    var finish = null; out.forEach(function (o) { if (o.finish && (!finish || o.finish > finish)) finish = o.finish; });
    // Critical path: from the most critical, latest-finishing activity back along driving relationships.
    var path = [];
    if (hasLogic) {
      var crit = acts.filter(function (x) { return x.critical; });
      if (crit.length) {
        var minTf = Math.min.apply(null, crit.map(function (x) { return x.tf; }));
        var end = crit.filter(function (x) { return x.tf === minTf; }).sort(function (p, q) { return (q.ef - p.ef) || (q.topo - p.topo); })[0];
        var seen = {}, cur = end;
        while (cur && !seen[cur.id]) {
          seen[cur.id] = true; path.push(cur.id);
          if (cur.status !== 'not_started' || cur.reason !== 'logic') break;
          var drivers = cur.inc.map(function (r) { return byId[r.pred]; }).filter(function (p, k) { return p.critical && req(cur.inc[k], p, cur) === cur.es; });
          drivers.sort(function (p, q) { return (p.tf - q.tf) || (q.ef - p.ef) || (q.topo - p.topo); });
          cur = drivers[0];
        }
        path.reverse();
      }
    } else warnings.push('Critical path not verifiable without logic.');
    return { activities: out, finish_date: finish, finish_index: pf, critical_path: path, warnings: warnings,
      data_date: dataDate, start: cal.dateOf(0), has_logic: hasLogic };
  }

  // ---------- quality ----------
  function quality(sched) {
    var acts = sched.activities || [], rels = sched.relationships || [], has = {}, out = [];
    acts.forEach(function (a) { has[String(a.id)] = true; });
    function add(check, ids, note, sev) {
      var u = ids.filter(function (x, i) { return ids.indexOf(x) === i; });
      out.push({ check: check, severity: u.length ? (sev || 'warn') : 'info', count: u.length, ids: u, note: note });
    }
    var valid = rels.filter(function (r) { return has[String(r.pred)] && has[String(r.succ)]; });
    var hasLogic = !sched.source || sched.source.has_logic !== false;
    if (!hasLogic) out.push({ check: 'Logic not available', severity: 'warn', count: acts.length, ids: [], note: 'Relationships could not be read, so open ends, float and the critical path cannot be checked.' });
    else {
      var r = cpm(sched), pos = {}; r.activities.forEach(function (o) { pos[o.id] = o; });
      var preds = {}, succs = {};
      valid.forEach(function (x) { succs[String(x.pred)] = true; preds[String(x.succ)] = true; });
      var noPred = acts.map(function (a) { return String(a.id); }).filter(function (id) { return !preds[id]; });
      var noSucc = acts.map(function (a) { return String(a.id); }).filter(function (id) { return !succs[id]; });
      var first = noPred.slice().sort(function (a, b) { return (pos[a].es - pos[b].es) || 0; })[0];
      var last = noSucc.slice().sort(function (a, b) { return (pos[b].ef - pos[a].ef) || 0; })[0];
      add('Missing predecessors (open start)', noPred.filter(function (id) { return id !== first; }), 'Every activity except the first (' + (first || 'none') + ') should have a predecessor.');
      add('Missing successors (open end)', noSucc.filter(function (id) { return id !== last; }), 'Every activity except the last (' + (last || 'none') + ') should have a successor; open ends hide float.');
    }
    add('Negative lags (leads)', valid.filter(function (x) { return num(x.lag) < 0; }).map(function (x) { return String(x.succ); }), 'Relationships with negative lag; ids are the successors.');
    add('Hard constraints', acts.filter(function (a) { return a.constraint && /^(MSO|MFO|FNLT)$/.test(a.constraint.type); }).map(function (a) { return String(a.id); }), 'MSO, MFO and FNLT constraints override logic and can create negative float.');
    add('Durations over 44 working days', acts.filter(function (a) { return (num(a.duration) || 0) > 44; }).map(function (a) { return String(a.id); }), 'Long activities should be broken down (DCMA 14-point, high duration).');
    var missing = rels.filter(function (x) { return !has[String(x.pred)] || !has[String(x.succ)]; });
    add('Relationships to missing activities', missing.map(function (x) { return has[String(x.succ)] ? String(x.succ) : String(x.pred); }), missing.map(function (x) { return x.pred + ' -> ' + x.succ; }).join(', ') || 'None.');
    var cyc = cycles(acts.map(function (a) { return String(a.id); }), valid.map(function (x) { return { pred: String(x.pred), succ: String(x.succ) }; }));
    add('Logic loops (cycles)', [].concat.apply([], cyc), cyc.map(function (c) { return c.join(' -> '); }).join('; ') || 'None.');
    return out;
  }

  // ---------- TIA ----------
  function tia(sched, fragnet) {
    fragnet = fragnet || {};
    var notes = [], ids = {};
    (sched.activities || []).forEach(function (a) { ids[String(a.id)] = true; });
    var copy = JSON.parse(JSON.stringify(sched));
    var added = [];
    (fragnet.activities || []).forEach(function (f) {
      var id = String(f.id);
      if (ids[id]) { notes.push('Fragnet activity ' + id + ' duplicates an existing id and was not inserted.'); return; }
      if (!/^F-/.test(id)) notes.push('Fragnet activity ' + id + ' does not start with "F-".');
      ids[id] = true; added.push(id);
      var a = blankActivity(id, f.name || ''); a.duration = num(f.duration) || 0; a.wbs = f.wbs || 'Fragnet';
      if (f.constraint) a.constraint = f.constraint;
      copy.activities.push(a);
    });
    (fragnet.relationships || []).forEach(function (r) {
      if (!ids[String(r.pred)] || !ids[String(r.succ)]) { notes.push('Fragnet link ' + r.pred + ' -> ' + r.succ + ' points to a missing activity and was ignored.'); return; }
      copy.relationships.push({ pred: String(r.pred), succ: String(r.succ), type: (r.type || 'FS').toUpperCase(), lag: num(r.lag) || 0 });
    });
    if (copy.source) copy.source.has_logic = copy.source.has_logic !== false || (fragnet.relationships || []).length > 0;
    var before = cpm(sched), after = cpm(copy);
    var dW = Math.max(0, after.finish_index - before.finish_index);
    var dC = before.finish_date && after.finish_date ? Math.max(0, calDays(before.finish_date, after.finish_date)) : 0;
    var res = {}; after.activities.forEach(function (o) { res[o.id] = o; });
    var fr = added.map(function (id) { var o = res[id]; return { id: id, start: o.start, finish: o.finish, total_float: o.total_float, critical: o.critical }; });
    var fCrit = fr.some(function (f) { return f.critical; });
    if (!before.has_logic) notes.push('The schedule has no logic: the impact is not verifiable from this schedule.');
    if (dW > 0) notes.push('Project finish moves from ' + before.finish_date + ' to ' + after.finish_date + ': ' + dW + ' working days, ' + dC + ' calendar days.');
    else notes.push('Project finish unchanged (' + before.finish_date + '); the fragnet is absorbed by float.');
    fr.forEach(function (f) { notes.push(f.id + ': ' + f.start + ' to ' + f.finish + ', total float ' + f.total_float + (f.critical ? ' (critical)' : '') + '.'); });
    var fdur = added.reduce(function (s, id) { return s + (num(res[id] && res[id].duration) || 0); }, 0);
    if (fdur > dW && dW > 0) notes.push('Float absorbed part of the fragnet: ' + dW + ' working days of delay against ' + fdur + ' working days of fragnet duration.');
    return { before_finish: before.finish_date, after_finish: after.finish_date, delay_workdays: dW, delay_calendar_days: dC,
      fragnet_critical: fCrit, driving_path: after.critical_path, notes: notes, fragnet: fr,
      warnings: after.warnings.filter(function (w) { return before.warnings.indexOf(w) < 0; }) };
  }

  var api = { parseXER: parseXER, parseMSPDI: parseMSPDI, parseCSV: parseCSV, parseRows: parseRows, cpm: cpm, quality: quality, tia: tia,
    parsePredecessors: parsePredecessors, parseXML: parseXML, makeCalendar: makeCalendar, readDate: readDate, splitCSV: splitCSV };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.ClauseSchedule = api;
})(this);
