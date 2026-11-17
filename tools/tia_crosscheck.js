// Cross-check: the browser schedule engine (assets/schedule.js) against the independent Python reference
// (demo4/cpm_ref.py) and the answer key, on the Demo 4 schedule in every format and all 15 change orders.
// node tools/tia_crosscheck.js
const fs = require('fs'), path = require('path');
const R = path.resolve(__dirname, '..'), D = path.join(R, 'demo4', 'data');
const SE = require(path.join(R, 'assets', 'schedule.js'));
let bad = 0, n = 0, ties = 0;
function eq(name, got, want) { n++; if (JSON.stringify(got) !== JSON.stringify(want)) { bad++; console.log('FAIL', name, '\n  js  ', JSON.stringify(got), '\n  want', JSON.stringify(want)); } }

const json = JSON.parse(fs.readFileSync(path.join(D, 'schedule.json'), 'utf8'));
const key = JSON.parse(fs.readFileSync(path.join(D, 'answer_key.json'), 'utf8'));
const cases = JSON.parse(fs.readFileSync(path.join(D, 'cases.json'), 'utf8')).cases;
const base = SE.cpm(json);
eq('json finish = key before_finish', base.finish_date, key.meta.forecast_finish_before);

// Every format reads to the same finish and critical path.
const opts = { data_date: json.data_date, calendar: json.calendar };
const XLSX = (() => { try { return require(path.join(R, 'assets', 'vendor', 'sheetjs', 'xlsx.mini.min.js')); } catch (e) { return null; } })();
const fmts = {
  xer: () => SE.parseXER(fs.readFileSync(path.join(D, 'schedule.xer'), 'latin1')),
  xml: () => SE.parseMSPDI(fs.readFileSync(path.join(D, 'schedule.xml'), 'utf8')),
  csv: () => SE.parseCSV(fs.readFileSync(path.join(D, 'schedule.csv'), 'utf8'), opts),
  xlsx: () => { const wb = XLSX.read(fs.readFileSync(path.join(D, 'schedule.xlsx')), { type: 'buffer' }); return SE.parseRows(XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { header: 1, raw: true, defval: '' }), opts); },
};
for (const [f, read] of Object.entries(fmts)) {
  if (f === 'xlsx' && !XLSX) { console.log('skip xlsx (no SheetJS)'); continue; }
  const s = read(), c = SE.cpm(s);
  eq(f + ' activities', s.activities.length, json.activities.length);
  eq(f + ' relationships', s.relationships.length, json.relationships.length);
  eq(f + ' finish', c.finish_date, base.finish_date);
  eq(f + ' critical path', c.critical_path, base.critical_path);
}
const nl = SE.parseCSV(fs.readFileSync(path.join(D, 'schedule_nologic.csv'), 'utf8'), opts);
eq('no-logic csv has_logic', nl.source.has_logic, false);

// Every change order: JS TIA vs the answer key (built with cpm_ref.py).
for (const k of key.cases) {
  const cp = cases.find(c => c.id === k.id);
  if (!cp.fragnet_truth || !cp.fragnet_truth.activities.length) { eq(k.id + ' no fragnet -> no delay', k.delay_calendar_days, 0); continue; }
  const r = SE.tia(json, cp.fragnet_truth);
  eq(k.id + ' TIA', [r.before_finish, r.after_finish, r.delay_workdays, r.delay_calendar_days, r.fragnet_critical],
    [k.before_finish, k.after_finish, k.delay_workdays, k.delay_calendar_days, k.fragnet_critical]);
  // Driving path: where two chains tie at zero float the engines may walk back through different ones. Both are right
  // if every activity on the key's path is also critical in the JS run.
  if (k.driving_path) {
    const m = JSON.parse(JSON.stringify(json)); cp.fragnet_truth.activities.forEach(a => m.activities.push({ id: a.id, name: a.name, duration: a.duration, wbs: 'F', actual_start: null, actual_finish: null, remaining: null, constraint: null }));
    m.relationships = m.relationships.concat(cp.fragnet_truth.relationships);
    const crit = {}; SE.cpm(m).activities.forEach(a => { crit[a.id] = a.critical; });
    eq(k.id + ' key driving path is critical in JS', k.driving_path.filter(id => !crit[id]), []);
    if (JSON.stringify(r.driving_path) !== JSON.stringify(k.driving_path)) ties++;
  }
}
if (ties) console.log(ties + ' cases: driving path differs only by a zero-float tie');
console.log(bad ? bad + ' of ' + n + ' checks FAILED' : 'tia crosscheck ok: ' + n + ' checks');
process.exit(bad ? 1 : 0);
