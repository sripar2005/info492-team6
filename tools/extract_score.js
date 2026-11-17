// Scores demo3/results/extract_test.json: for each sample PDF, how many fields the local model read
// correctly, and whether the checklist built from what it read matches the checklist on the real
// proposal. Writes demo3/results/extract_score.json. Run from the repo root: node tools/extract_score.js
const C = require('../assets/checks.js');
const fs = require('fs'), path = require('path');
const R = p => JSON.parse(fs.readFileSync(path.join(__dirname, '..', p), 'utf8'));
const cases = Object.fromEntries(R('demo3/data/cases.json').cases.map(c => [c.id, c]));
const test = R('demo3/results/extract_test.json');
const near = (a, b) => Math.abs((+a || 0) - (+b || 0)) < 0.011;
const out = [];
for (const r of test.results) {
  const id = r.file.slice(0, 7), want = C.toForm(cases[id]);
  if (r.error) { out.push({ file: r.file, error: r.error }); continue; }
  const got = r.form, fields = [];
  const cmp = (name, a, b, eq) => fields.push({ field: name, expected: a, got: b, ok: (eq || ((x, y) => x === y))(a, b) });
  ['title', 'cause', 'event_date', 'notice_date'].forEach(k => cmp(k, want[k], got[k], (a, b) => String(a).trim().toLowerCase() === String(b).trim().toLowerCase()));
  ['time_days', 'cm_direct', 'nss', 'sgc', 'bond', 'bo', 'permits', 'ext_sgc', 'fee_pct', 'fee_amount', 'total'].forEach(k => cmp(k, want[k], got[k], near));
  cmp('fee_on', want.fee_on.slice().sort().join('|'), (got.fee_on || []).slice().sort().join('|'));
  cmp('subcontractor count', want.subs.length, (got.subs || []).length);
  want.subs.forEach((s, i) => {
    const g = (got.subs || [])[i] || {};
    cmp(`sub ${i + 1} email only`, !!s.email_only, !!g.email_only);
    if (s.email_only) return cmp(`sub ${i + 1} quote total`, s.quote_total, g.quote_total, near);
    ['own_cost', 'own_markup_pct', 'lower_cost', 'lower_markup_pct'].forEach(k => cmp(`sub ${i + 1} ${k}`, s[k], g[k], near));
    cmp(`sub ${i + 1} breakdown`, !!s.breakdown, !!g.breakdown);
    cmp(`sub ${i + 1} unsigned T&M tags`, s.tm_tags.filter(t => !t.signed).length, (g.tm_tags || []).filter(t => !t.signed).length);
  });
  cmp('labor lines', want.labor.length, (got.labor || []).length);
  want.labor.forEach((l, i) => cmp(`labor ${i + 1} burden %`, l.burden_pct, ((got.labor || [])[i] || {}).burden_pct, near));
  // The checklist on what was read vs on the real proposal: same route and same flags?
  const f = Object.assign(C.toForm(cases[id]), {}); // start from structure, overwrite with what was read
  Object.assign(f, got, { _order: null, _other_lines: [] });
  f.subs = (got.subs || []).map(s => Object.assign({ tm_tags: [] }, s));
  f.labor = got.labor || []; f.equipment = got.equipment || [];
  const read = C.checksheet(C.toCase(f)), real = C.checksheet(cases[id]);
  const flags = s => s.rows.filter(x => x.flag).map(x => x.flag).sort().join(',');
  out.push({ file: r.file, seconds: r.seconds, fields_right: fields.filter(x => x.ok).length, fields: fields.length,
    wrong: fields.filter(x => !x.ok), verdict_same: read.route === real.route && flags(read) === flags(real),
    real: { route: real.route, flags: flags(real) }, read: { route: read.route, flags: flags(read) } });
}
fs.writeFileSync(path.join(__dirname, '..', 'demo3/results/extract_score.json'), JSON.stringify({ model: test.model, results: out }, null, 1));
for (const o of out) console.log(o.file, o.error || `${o.fields_right}/${o.fields} fields, same verdict: ${o.verdict_same} (${o.seconds}s)`, o.wrong ? o.wrong.map(w => `${w.field}: want ${w.expected} got ${w.got}`).join('; ') : '');
