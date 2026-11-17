// Runs the browser checks (assets/checks.js) on all 36 test proposals and compares them with the
// Python results in demo3/results/checksheets.json. Also round-trips each proposal through the
// editable form format and requires the same result. Exit code 1 on any difference.
const C = require('../assets/checks.js');
const fs = require('fs'), path = require('path');
const R = p => JSON.parse(fs.readFileSync(path.join(__dirname, '..', p), 'utf8'));
const cases = R('demo3/data/cases.json').cases, py = R('demo3/results/checksheets.json').sheets;
const key = s => JSON.stringify({ route: s.route, at: s.dollars_at_issue, counts: s.counts,
  rows: s.rows.map(r => [r.check, r.section, r.status, r.flag, r.difference, r.contract, r.proposal]) });
let bad = 0;
for (const cp of cases) {
  const js = C.checksheet(cp), rt = C.checksheet(Object.assign(C.toCase(C.toForm(cp)), { id: cp.id, title: cp.title }));
  if (key(js) !== key(py[cp.id])) { bad++; console.log('JS != Python', cp.id); const a = JSON.parse(key(js)), b = JSON.parse(key(py[cp.id])); a.rows.forEach((r, i) => { if (JSON.stringify(r) !== JSON.stringify(b.rows[i])) console.log('  js', JSON.stringify(r), '\n  py', JSON.stringify(b.rows[i])); }); if (a.route !== b.route || a.at !== b.at) console.log(' ', a.route, b.route, a.at, b.at); }
  if (key(rt) !== key(js)) { bad++; console.log('form round-trip differs', cp.id); }
}
// A few form edits behave as a person would expect.
const f = C.toForm(cases.find(c => c.id === 'CP-0201')); f.subs[0].own_markup_pct = 15; C.recompute(f);
const s = C.checksheet(C.toCase(f)); const m = s.rows.find(r => r.flag === 'SUB_MARKUP');
if (!m || !(m.difference > 0) || s.rows.some(r => r.flag === 'TIEOUT')) { bad++; console.log('edit test failed', JSON.stringify(m)); }
console.log(bad ? `${bad} mismatches` : `parity ok: ${cases.length} proposals match Python, form round-trip ok, edit test ok`);
process.exit(bad ? 1 : 0);
