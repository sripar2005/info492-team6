// Scores the platform's code checks against the answer key the separate data helper wrote (record/platform/answer_key.json).
// The helper never saw this code. node tools/platform_test.js
var fs = require('fs'), R = require('../assets/rules.js');
var PL = JSON.parse(fs.readFileSync('record/platform/platform.json', 'utf8')), KEY = JSON.parse(fs.readFileSync('record/platform/answer_key.json', 'utf8'));
var TK = JSON.parse(fs.readFileSync('demo4/data/contract_terms_key.json', 'utf8')).contracts.A.terms;
var cases = {}; ['demo3/data/cases.json', 'demo4/data/cases.json'].forEach(function (f) { JSON.parse(fs.readFileSync(f, 'utf8')).cases.forEach(function (c) { cases[c.id] = c; }); });
var right = 0, wrong = [];
function check(ok, what) { if (ok) right++; else wrong.push(what); }

// Flow-down gaps: the prime notice window is the shortest window in § 6.2.
var byCause = TK.notice_days_by_cause.value, primeDays = Math.min.apply(null, Object.keys(byCause).map(function (k) { return byCause[k]; }));
PL.contracts.filter(function (k) { return k.kind === 'sub'; }).forEach(function (k) {
  var t = (k.terms || []).filter(function (x) { return x.key === 'notice_days'; })[0], key = KEY.flowdown_gaps.subs[k.key];
  if (!t || !key) return;
  var g = R.flowdownGap(primeDays, +t.value);
  check(g.gap === !!key.gap, 'flow-down ' + k.key + ': code ' + g.gap + ', key ' + key.gap);
});
// Cost per day.
var cpd = R.costPerDay(PL.sov.filter(function (l) { return l.contract === 'prime'; }), TK.daily_delay_rate.value, TK.contract_days.value);
check(Math.abs(cpd.spread - KEY.cost_per_day.sov_cost_per_day) < 0.01, 'cost per day: code ' + cpd.spread + ', key ' + KEY.cost_per_day.sov_cost_per_day);
check(cpd.stated === KEY.cost_per_day.contract_stated_rate, 'stated rate');
// Roll-ups: each change's sub requests against the case's subcontractor quotes.
Object.keys(KEY.rollups).forEach(function (cp) {
  var reqs = PL.sub_requests.filter(function (s) { return s.change === cp; }), c = cases[cp]; if (!c) return;
  var quotes = (c.subcontractor_quotes || []).reduce(function (s, q) { return s + (+q.quote_total || 0); }, 0);
  var r = R.rollup(reqs, quotes);
  check(r.match === KEY.rollups[cp].match, 'roll-up ' + cp + ': code ' + r.match + ' (' + r.total + ' vs ' + quotes + '), key ' + KEY.rollups[cp].match);
});
// Visibility of sub requests once sent.
var role = { owner: 'owner', architect: 'architect', gc: 'gc' };
Object.keys(KEY.visibility.by_company).forEach(function (co) {
  var r = role[co] || 'sub', seen = PL.sub_requests.filter(function (s) { return R.seesChange({ tier: 'sub_request', status: 'with_gc', from_company: s.from, to_company: s.to }, co, r); }).map(function (s) { return s.key; }).sort();
  var want = KEY.visibility.by_company[co].slice().sort();
  check(JSON.stringify(seen) === JSON.stringify(want), 'visibility ' + co);
});
console.log('platform checks vs answer key: ' + right + ' right, ' + wrong.length + ' wrong');
wrong.forEach(function (w) { console.log('  WRONG: ' + w); });
process.exit(wrong.length ? 1 : 0);
