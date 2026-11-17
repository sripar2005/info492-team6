#!/usr/bin/env node
/* Tests for assets/schedule.js. Every expected value below was worked out by hand (see the comments);
 * none is copied from the engine's own output. Run: node tools/schedule_test.js  (exit 1 on any failure). */
'use strict';
var fs = require('fs'), path = require('path');
var S = require('../assets/schedule.js');
var FIX = path.join(__dirname, 'fixtures');

var pass = 0, fail = 0, group = '';
function same(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
function eq(actual, expected, label) {
  if (same(actual, expected)) pass++;
  else { fail++; console.log('  FAIL [' + group + '] ' + label + '\n    expected ' + JSON.stringify(expected) + '\n    actual   ' + JSON.stringify(actual)); }
}
function ok(cond, label) { eq(!!cond, true, label); }
function test(name, fn) { group = name; var f0 = fail; try { fn(); } catch (e) { fail++; console.log('  FAIL [' + name + '] threw ' + (e.stack || e)); } console.log((fail === f0 ? 'ok   ' : 'FAIL ') + name); }

// Build a schedule from compact rows: [id, duration, [[pred, type, lag], ...], extra]
function sched(start, rows, o) {
  o = o || {};
  var acts = [], rels = [];
  rows.forEach(function (r) {
    acts.push(Object.assign({ id: r[0], name: r[0], duration: r[1], wbs: '', actual_start: null, actual_finish: null, remaining: null, constraint: null }, r[3] || {}));
    (r[2] || []).forEach(function (p) { rels.push({ pred: p[0], succ: r[0], type: p[1] || 'FS', lag: p[2] || 0 }); });
  });
  return { name: 't', data_date: o.data_date || null, start: start, calendar: { workdays: [1, 2, 3, 4, 5], holidays: o.holidays || [] },
    activities: acts, relationships: rels, source: { format: 'test', file: '', has_logic: o.has_logic !== false } };
}
function byId(res) { var m = {}; res.activities.forEach(function (a) { m[a.id] = a; }); return m; }
function pick(a) { return [a.es, a.ef, a.ls, a.lf, a.total_float]; }

// ---------------------------------------------------------------------------------------------
test('simple FS chain', function () {
  // Start Mon 2020-03-02. A(3): days 0-2 = 3/2-3/4. B(2): 3-4 = 3/5-3/6. C(4): 5-8 = Mon 3/9 - Thu 3/12.
  var r = S.cpm(sched('2020-03-02', [['A', 3], ['B', 2, [['A']]], ['C', 4, [['B']]]])), m = byId(r);
  eq(pick(m.A), [0, 3, 0, 3, 0], 'A'); eq(pick(m.B), [3, 5, 3, 5, 0], 'B'); eq(pick(m.C), [5, 9, 5, 9, 0], 'C');
  eq([m.B.start, m.B.finish, m.C.start, m.C.finish], ['2020-03-05', '2020-03-06', '2020-03-09', '2020-03-12'], 'dates cross a weekend');
  eq(r.finish_date, '2020-03-12', 'finish date'); eq(r.critical_path, ['A', 'B', 'C'], 'critical path'); eq(r.warnings, [], 'no warnings');
});

test('parallel paths, one critical', function () {
  // S -> X(5) -> E and S -> Y(3) -> E. X drives E (ES 5); Y has 5 - 3 = 2 days of float.
  var r = S.cpm(sched('2020-03-02', [['S', 0], ['X', 5, [['S']]], ['Y', 3, [['S']]], ['E', 0, [['X'], ['Y']]]])), m = byId(r);
  eq(pick(m.X), [0, 5, 0, 5, 0], 'X'); eq(pick(m.Y), [0, 3, 2, 5, 2], 'Y'); eq(m.Y.critical, false, 'Y not critical');
  eq(m.Y.late_finish, '2020-03-06', 'Y late finish'); eq(m.E.finish, '2020-03-06', 'finish milestone on Friday');
  eq(r.critical_path, ['S', 'X', 'E'], 'critical path');
});

test('SS/FF/SF/FS with positive and negative lags', function () {
  // K(4) 0-4; P(5) FS K: 4-9 (PF = 9).
  // Q(3) SF+2: EF >= P.ES+2 = 6 -> 3-6, LF 9, TF 3.     R(2) SS-2: ES >= 4-2 = 2 -> 2-4, LF 9, TF 5.
  // T(3) FF-1: EF >= 9-1 = 8 -> 5-8, TF 1.               U(2) FS-2: ES >= 9-2 = 7 -> 7-9, TF 0.
  // V(2) SF-1: EF >= 4-1 = 3 -> 1-3, TF 6.               W(3) SS+1: ES >= 5 -> 5-8, TF 1.
  // Backward on P: U FS-2 gives LF <= 7+2 = 9 (tightest; T FF-1 gives 10, W SS+1 gives 6-1+5 = 10).
  var r = S.cpm(sched('2020-03-02', [['K', 4], ['P', 5, [['K']]], ['Q', 3, [['P', 'SF', 2]]], ['R', 2, [['P', 'SS', -2]]],
    ['T', 3, [['P', 'FF', -1]]], ['U', 2, [['P', 'FS', -2]]], ['V', 2, [['P', 'SF', -1]]], ['W', 3, [['P', 'SS', 1]]]])), m = byId(r);
  eq(pick(m.K), [0, 4, 0, 4, 0], 'K'); eq(pick(m.P), [4, 9, 4, 9, 0], 'P');
  eq(pick(m.Q), [3, 6, 6, 9, 3], 'Q SF+2'); eq(pick(m.R), [2, 4, 7, 9, 5], 'R SS-2'); eq(pick(m.T), [5, 8, 6, 9, 1], 'T FF-1');
  eq(pick(m.U), [7, 9, 7, 9, 0], 'U FS-2'); eq(pick(m.V), [1, 3, 7, 9, 6], 'V SF-1'); eq(pick(m.W), [5, 8, 6, 9, 1], 'W SS+1');
  eq([m.Q.start, m.Q.finish, m.U.start, m.U.finish], ['2020-03-05', '2020-03-09', '2020-03-11', '2020-03-12'], 'dates');
  eq(r.critical_path, ['K', 'P', 'U'], 'critical path follows the FS-2 link');
});

test('holiday shifts dates', function () {
  // A(3) from Fri 2020-05-22: 5/22, (weekend), 5/25 Memorial Day off, 5/26, 5/27. B(1) FS: 5/28.
  var r = S.cpm(sched('2020-05-22', [['A', 3], ['B', 1, [['A']]]], { holidays: ['2020-05-25'] })), m = byId(r);
  eq([m.A.finish, m.B.start, r.finish_date], ['2020-05-27', '2020-05-28', '2020-05-28'], 'with holiday');
  var r2 = S.cpm(sched('2020-05-22', [['A', 3], ['B', 1, [['A']]]])), m2 = byId(r2);
  eq([m2.A.finish, m2.B.start], ['2020-05-26', '2020-05-27'], 'without holiday');
});

test('milestones', function () {
  // NTP(0) -> A(5) -> DONE(0). NTP on day 0 (start milestone, 3/2); DONE ES = EF = 5 is a finish milestone
  // shown on A's last day, Fri 3/6. The finish date is 3/6, not Mon 3/9.
  var r = S.cpm(sched('2020-03-02', [['NTP', 0], ['A', 5, [['NTP']]], ['DONE', 0, [['A']]]])), m = byId(r);
  eq([m.NTP.es, m.NTP.ef, m.NTP.start, m.NTP.finish], [0, 0, '2020-03-02', '2020-03-02'], 'start milestone');
  eq([m.DONE.es, m.DONE.ef, m.DONE.start, m.DONE.finish, m.DONE.total_float], [5, 5, '2020-03-06', '2020-03-06', 0], 'finish milestone');
  eq(r.finish_date, '2020-03-06', 'finish date'); eq(r.critical_path, ['NTP', 'A', 'DONE'], 'path includes milestones');
});

test('SNET, FNLT and MSO constraints', function () {
  // A(2) 0-2. B(3) FS A with SNET Tue 3/10 (day 6): 6-9 = 3/10-3/12. C(2) FS B: 9-11 = Fri 3/13 - Mon 3/16, but
  // FNLT Fri 3/13 -> LF = 10, TF = -1 (violated). B: LF <= C.LS = 8 -> TF -1. A: LF <= B.LS = 5 -> TF 3.
  // D(1) FS A with MSO Tue 3/3 (day 1) is earlier than logic (day 2): the constraint wins, with a warning.
  // E(1) FS A with SNET Mon 3/2 (earlier than logic): logic wins, ES 2.
  var s = sched('2020-03-02', [['A', 2], ['B', 3, [['A']], { constraint: { type: 'SNET', date: '2020-03-10' } }],
    ['C', 2, [['B']], { constraint: { type: 'FNLT', date: '2020-03-13' } }],
    ['D', 1, [['A']], { constraint: { type: 'MSO', date: '2020-03-03' } }],
    ['E', 1, [['A']], { constraint: { type: 'SNET', date: '2020-03-02' } }]]);
  var r = S.cpm(s), m = byId(r);
  eq([m.B.es, m.B.start, m.B.finish], [6, '2020-03-10', '2020-03-12'], 'SNET delays B');
  eq(pick(m.C), [9, 11, 8, 10, -1], 'C FNLT gives negative float'); eq(pick(m.B), [6, 9, 5, 8, -1], 'B float -1'); eq(pick(m.A), [0, 2, 3, 5, 3], 'A float 3');
  eq([m.D.es, m.D.start], [1, '2020-03-03'], 'MSO holds'); eq(m.E.es, 2, 'early SNET has no effect');
  ok(r.warnings.some(function (w) { return /Finish-no-later-than 2020-03-13 on C is violated/.test(w); }), 'FNLT violation flagged');
  ok(r.warnings.some(function (w) { return /MSO 2020-03-03\) on D/.test(w); }), 'MSO violation flagged');
  eq(r.critical_path, ['B', 'C'], 'path starts at the constrained activity');
  // Mandatory finish: same as FNLT on the backward pass.
  var r2 = S.cpm(sched('2020-03-02', [['A', 2], ['B', 3, [['A']], { constraint: { type: 'MFO', date: '2020-03-06' } }]]));
  eq(pick(byId(r2).B), [2, 5, 2, 5, 0], 'MFO on its early finish: float 0');
});

test('in-progress activity uses remaining duration from the data date', function () {
  // Start Mon 3/2, data date Mon 3/9 (day 5). A(3) complete 3/2-3/4. B(6) started Thu 3/5 (day 3), 4 days remain:
  // remaining work days 5-8 -> finish Thu 3/12. C(2) FS B: days 9-10 = 3/13-3/16. D(2) FS A not started: can't start
  // before the data date -> day 5 (3/9), TF = 11 - 7 = 4.
  var s = sched('2020-03-02', [['A', 3, [], { actual_start: '2020-03-02', actual_finish: '2020-03-04' }],
    ['B', 6, [['A']], { actual_start: '2020-03-05', remaining: 4 }], ['C', 2, [['B']]], ['D', 2, [['A']]]], { data_date: '2020-03-09' });
  var r = S.cpm(s), m = byId(r);
  eq([m.A.status, m.A.total_float, m.A.critical, m.A.start, m.A.finish], ['complete', null, false, '2020-03-02', '2020-03-04'], 'A complete');
  eq([m.B.status, m.B.es, m.B.ef, m.B.start, m.B.finish, m.B.remaining, m.B.total_float], ['in_progress', 3, 9, '2020-03-05', '2020-03-12', 4, 0], 'B in progress');
  eq([m.C.start, m.C.finish, m.C.total_float], ['2020-03-13', '2020-03-16', 0], 'C');
  eq([m.D.start, m.D.total_float], ['2020-03-09', 4], 'D held at data date');
  eq(r.critical_path, ['B', 'C'], 'critical path starts at in-progress activity'); eq(r.finish_date, '2020-03-16', 'finish');
});

test('cycle detected without looping', function () {
  var s = sched('2020-03-02', [['A', 1, [['C']]], ['B', 1, [['A']]], ['C', 1, [['B']]], ['D', 1, [['C']]]]);
  var r = S.cpm(s);
  ok(r.warnings.some(function (w) { return /cycle/.test(w) && /A, B, C/.test(w); }), 'cycle warning names A, B, C');
  eq(r.activities.length, 4, 'all activities scheduled');
  var q = S.quality(s).filter(function (c) { return /cycles/.test(c.check); })[0];
  eq([q.count, q.ids.slice().sort(), q.severity], [3, ['A', 'B', 'C'], 'warn'], 'quality cycle check');
});

test('quality checks', function () {
  // S start; A(50) too long; B SS-1 negative lag; C MSO hard constraint; E links to missing ZZZ; X dangling both ends.
  var s = sched('2020-03-02', [['S', 0], ['A', 50, [['S']]], ['B', 2, [['A', 'SS', -1]]],
    ['C', 3, [['A']], { constraint: { type: 'MSO', date: '2020-06-01' } }], ['D', 1, [['C']]], ['E', 1, [['ZZZ'], ['D']]],
    ['X', 1], ['F', 0, [['E'], ['B']]]]);
  var q = {}; S.quality(s).forEach(function (c) { q[c.check] = c; });
  eq(q['Missing predecessors (open start)'].ids, ['X'], 'open starts exclude the first activity');
  eq(q['Missing successors (open end)'].ids, ['X'], 'open ends exclude the last activity');
  eq(q['Negative lags (leads)'].ids, ['B'], 'negative lag'); eq(q['Hard constraints'].ids, ['C'], 'hard constraint');
  eq(q['Durations over 44 working days'].ids, ['A'], 'long duration');
  eq([q['Relationships to missing activities'].ids, q['Relationships to missing activities'].note], [['E'], 'ZZZ -> E'], 'missing link');
  eq([q['Logic loops (cycles)'].count, q['Logic loops (cycles)'].severity], [0, 'info'], 'no cycles');
  var nl = S.quality(sched('2020-03-02', [['A', 1]], { has_logic: false }));
  eq(nl[0].check, 'Logic not available', 'no-logic schedule flagged');
});

// ---------------------------------------------------------------------------------------------
// Fixture: the same 9-activity schedule as XER, MSPDI XML and CSV (tools/fixtures/school.*).
// Start Mon 2020-02-03, Mon-Fri, holiday Mon 2020-02-17. Hand CPM (working day: date):
// 0 2/3 .. 4 2/7, 5 2/10 .. 9 2/14, [2/17 off], 10 2/18 .. 13 2/21, 14 2/24 .. 18 2/28, 19 3/2 .. 23 3/6,
// 24 3/9 .. 28 3/13, 29 3/16, 30 3/17, 31 3/18, 32 3/19, 33 3/20, 34 3/23.
//   A1000 NTP 0      0-0              A1010 Mobilize 5 FS       0-5
//   A1020 Excav 10   FS A1010 5-15    A1030 Utilities 4 SS+2    2-6   LF 15 TF 9
//   A1040 Found 8    FS both 15-23    A1050 Steel fab 15 FS A1000 0-15 LF 21 TF 6 (FS+2 into A1060)
//   A1060 Erect 6    23-29            A1070 Inspect 2 FF+1      EF 30, ES 28
//   A1099 SC 0       30-30  -> finish = day 29 = 2020-03-16; A1020 finishes 2/24 (2/21 without the holiday).
var FX = {
  xer: fs.readFileSync(path.join(FIX, 'school.xer'), 'utf8'),
  xml: fs.readFileSync(path.join(FIX, 'school.xml'), 'utf8'),
  csv: fs.readFileSync(path.join(FIX, 'school.csv'), 'utf8')
};
var CSV_OPTS = { name: 'Fixture school', data_date: '2020-02-03', calendar: { workdays: [1, 2, 3, 4, 5], holidays: ['2020-02-17'] }, file: 'school.csv' };
var models = {
  xer: S.parseXER(FX.xer, { file: 'school.xer' }),
  mspdi: S.parseMSPDI(FX.xml, { file: 'school.xml' }),
  csv: S.parseCSV(FX.csv, CSV_OPTS)
};
// Spreadsheet rows as SheetJS sheet_to_json gives them (objects; Excel serial dates).
var rowObjs = S.splitCSV(FX.csv).slice(1).map(function (r) {
  var serial = function (d) { var iso = S.readDate(d).date; return (Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / 86400000) + 25569; };
  return { 'Activity ID': r[0], 'Activity Name': r[1], 'Original Duration (d)': r[2], Start: serial(r[3]), Finish: serial(r[4]), Predecessors: r[5], WBS: r[6] };
});
models.rows = S.parseRows(rowObjs, Object.assign({}, CSV_OPTS, { format: 'xlsx' }));
function core(m) { var c = JSON.parse(JSON.stringify(m)); delete c.source; return c; }

test('fixture: XER, MSPDI, CSV and rows give the same model', function () {
  var x = models.xer;
  eq([x.name, x.data_date, x.start, x.calendar], ['Fixture school', '2020-02-03', '2020-02-03', { workdays: [1, 2, 3, 4, 5], holidays: ['2020-02-17'] }], 'XER header + calendar');
  eq(x.activities.map(function (a) { return a.id + ':' + a.duration; }), ['A1000:0', 'A1010:5', 'A1020:10', 'A1030:4', 'A1040:8', 'A1050:15', 'A1060:6', 'A1070:2', 'A1099:0'], 'XER ids and durations');
  eq(x.relationships.length, 10, 'XER relationships');
  eq(x.relationships.filter(function (r) { return r.type !== 'FS' || r.lag; }), [{ pred: 'A1010', succ: 'A1030', type: 'SS', lag: 2 },
    { pred: 'A1050', succ: 'A1060', type: 'FS', lag: 2 }, { pred: 'A1060', succ: 'A1070', type: 'FF', lag: 1 }], 'XER typed links and lags');
  eq(x.activities[2].wbs, 'Site Work', 'XER WBS name'); eq(x.source.has_logic, true, 'has logic');
  eq(core(models.mspdi), core(x), 'MSPDI == XER'); eq(core(models.csv), core(x), 'CSV == XER'); eq(core(models.rows), core(x), 'rows == XER');
  eq([models.xer.source.warnings, models.mspdi.source.warnings, models.csv.source.warnings], [[], [], []], 'no parser warnings');
});

test('fixture: CPM identical across formats and matches hand values', function () {
  var expect = { A1000: [0, 0, 0, 0, 0], A1010: [0, 5, 0, 5, 0], A1020: [5, 15, 5, 15, 0], A1030: [2, 6, 11, 15, 9], A1040: [15, 23, 15, 23, 0],
    A1050: [0, 15, 6, 21, 6], A1060: [23, 29, 23, 29, 0], A1070: [28, 30, 28, 30, 0], A1099: [30, 30, 30, 30, 0] };
  var base = S.cpm(models.xer);
  Object.keys(models).forEach(function (k) {
    var r = S.cpm(models[k]), m = byId(r);
    Object.keys(expect).forEach(function (id) { eq(pick(m[id]), expect[id], k + ' ' + id); });
    eq(r.finish_date, '2020-03-16', k + ' finish'); eq(r.critical_path, ['A1000', 'A1010', 'A1020', 'A1040', 'A1060', 'A1070', 'A1099'], k + ' critical path');
    eq(r, base, k + ' full CPM result equals XER result');
  });
  var m = byId(base);
  eq([m.A1020.start, m.A1020.finish], ['2020-02-10', '2020-02-24'], 'holiday pushes Excavation finish from 2/21 to 2/24');
  eq([m.A1070.start, m.A1070.finish, m.A1099.finish], ['2020-03-13', '2020-03-16', '2020-03-16'], 'FF+1 inspection and finish milestone');
  // Parsed planned dates agree with the computed dates (fixtures were written from the hand computation).
  models.xer.activities.forEach(function (a) { eq([a.start, a.finish], [m[a.id].start, m[a.id].finish], 'planned = computed ' + a.id); });
});

test('CSV without predecessors: no logic, no critical path', function () {
  var text = 'ID,Name,Duration,Start,Finish\nA,Dig,3,2020-03-02,2020-03-04\nB,"Pour, cure",2,03/09/2020,03/10/2020\n';
  var s = S.parseCSV(text);
  eq([s.source.has_logic, s.relationships.length, s.activities[1].name], [false, 0, 'Pour, cure'], 'quoted comma kept, no logic');
  var r = S.cpm(s), m = byId(r);
  eq(r.critical_path, [], 'critical path empty'); ok(r.warnings.some(function (w) { return /not verifiable/.test(w); }), 'warning says not verifiable');
  eq([m.B.start, m.B.finish, r.finish_date], ['2020-03-09', '2020-03-10', '2020-03-10'], 'dates from planned starts');
  eq(r.activities.some(function (a) { return a.critical; }), false, 'nothing flagged critical');
});

test('predecessor strings', function () {
  eq(S.parsePredecessors('A1010FS+2, A1020SS, A1030'), [{ pred: 'A1010', type: 'FS', lag: 2 }, { pred: 'A1020', type: 'SS', lag: 0 }, { pred: 'A1030', type: 'FS', lag: 0 }], 'P6 style');
  eq(S.parsePredecessors('3FS+2 days; 5SS-1d;7FF'), [{ pred: '3', type: 'FS', lag: 2 }, { pred: '5', type: 'SS', lag: -1 }, { pred: '7', type: 'FF', lag: 0 }], 'MS Project style');
  eq(S.parsePredecessors('A1010 SF -16h'), [{ pred: 'A1010', type: 'SF', lag: -2 }], 'hours lag');
});

test('XML reader tolerates namespaces, CDATA, attributes and entities', function () {
  var d = S.parseXML('<?xml version="1.0"?><p:Project xmlns:p="x"><Name><![CDATA[A & B <1>]]></Name><T a="1 &amp; 2"/><Q>x &lt; y</Q></p:Project>');
  var p = d.children[0];
  eq([p.name, p.children[0].text, p.children[1].attrs.a, p.children[2].text], ['Project', 'A & B <1>', '1 & 2', 'x < y'], 'parsed');
});

// ---------------------------------------------------------------------------------------------
test('TIA: fragnet on the critical path adds its full duration', function () {
  // F-1 (3 days) between Foundations and Erect steel: A1060 moves from day 23 to 26, finish day 29 -> 32 = Thu 3/19.
  var t = S.tia(models.xer, { activities: [{ id: 'F-1', name: 'Redesign footing', duration: 3 }],
    relationships: [{ pred: 'A1040', succ: 'F-1', type: 'FS', lag: 0 }, { pred: 'F-1', succ: 'A1060', type: 'FS', lag: 0 }] });
  eq([t.before_finish, t.after_finish, t.delay_workdays, t.delay_calendar_days, t.fragnet_critical], ['2020-03-16', '2020-03-19', 3, 3, true], 'impact');
  eq(t.driving_path, ['A1000', 'A1010', 'A1020', 'A1040', 'F-1', 'A1060', 'A1070', 'A1099'], 'driving path runs through F-1');
});

test('TIA: fragnet within float adds nothing', function () {
  // F-2 (4) after Fabricate steel (EF 15) into Erect steel (ES 23): ends day 19, 4 days of float left.
  var t = S.tia(models.xer, { activities: [{ id: 'F-2', name: 'Re-detail connections', duration: 4 }],
    relationships: [{ pred: 'A1050', succ: 'F-2', type: 'FS', lag: 0 }, { pred: 'F-2', succ: 'A1060', type: 'FS', lag: 0 }] });
  eq([t.after_finish, t.delay_workdays, t.delay_calendar_days, t.fragnet_critical, t.fragnet[0].total_float], ['2020-03-16', 0, 0, false, 4], 'absorbed');
});

test('TIA: fragnet partially consumes float (and crosses a weekend)', function () {
  // F-3 (13) after Fabricate steel: EF 28 vs. A1060 ES 23 -> 8 days of float used, 5 days of delay.
  // Finish day 29 (Mon 3/16) -> day 34 (Mon 3/23): 5 working days, 7 calendar days.
  var t = S.tia(models.xer, { activities: [{ id: 'F-3', name: 'Re-fabricate steel', duration: 13 }],
    relationships: [{ pred: 'A1050', succ: 'F-3', type: 'FS', lag: 0 }, { pred: 'F-3', succ: 'A1060', type: 'FS', lag: 0 }] });
  eq([t.after_finish, t.delay_workdays, t.delay_calendar_days, t.fragnet_critical], ['2020-03-23', 5, 7, true], 'partial');
  eq(t.driving_path, ['A1000', 'A1050', 'F-3', 'A1060', 'A1070', 'A1099'], 'driving path switches to the steel path');
  ok(t.notes.some(function (n) { return /5 working days of delay against 13/.test(n); }), 'note explains absorbed float');
  // Same result from the MSPDI and CSV models.
  [models.mspdi, models.csv].forEach(function (m) { var u = S.tia(m, { activities: [{ id: 'F-3', duration: 13 }], relationships: [{ pred: 'A1050', succ: 'F-3' }, { pred: 'F-3', succ: 'A1060' }] });
    eq([u.delay_workdays, u.delay_calendar_days], [5, 7], m.source.format + ' TIA'); });
});

test('TIA input does not change the schedule', function () {
  var before = JSON.stringify(models.xer);
  S.tia(models.xer, { activities: [{ id: 'F-9', duration: 2 }], relationships: [{ pred: 'A1099', succ: 'F-9' }] });
  eq(JSON.stringify(models.xer), before, 'schedule untouched');
});

console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
