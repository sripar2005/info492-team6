// Keeps assets/contract.js in step with demo4/contract_extract.py: same sentences, sections and candidate sentences.
// node tools/contract_parity.js
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const R = path.resolve(__dirname, '..');
const J = require(path.join(R, 'assets', 'contract.js'));
const files = ['demo1/data/synthetic_contract.md', 'demo4/data/contract_b.md'].filter(f => fs.existsSync(path.join(R, f)));
let bad = 0;
for (const f of files) {
  const py = JSON.parse(execFileSync('python3', ['-c', `
import sys, json; sys.path.insert(0, 'demo4')
import contract_extract as ce
s = ce.sentences(open(${JSON.stringify(f)}).read())
_, _, _, c = ce.build_request(s)
H = ce.headings(open(${JSON.stringify(f)}).read())
vals = {"pct": [5, 8, 10, 25], "money": [2500, 150000, 3185], "days": [7, 14, 540], "bool": [True, False], "parties": [["owner"], ["owner", "architect"]], "concurrent": ["time_no_money", "no_time_no_money", "apportioned"], "fee_on": [["CM direct costs"]]}
v = {}
for key, _, kind, _, _ in ce.TERMS:
    for x in c[key]:
        for val in vals[kind]:
            v[key + "|" + x["id"] + "|" + json.dumps(val)] = list(ce.verify(key, kind, val, x, ce.context_for(x, s, H)))
print(json.dumps({"s": s, "c": {k: [x["id"] for x in v] for k, v in c.items()}, "v": v}))`], { cwd: R }).toString());
  const js = J.retrieve(fs.readFileSync(path.join(R, f), 'utf8'));
  if (JSON.stringify(js.sentences) !== JSON.stringify(py.s)) {
    bad++; const i = js.sentences.findIndex((s, k) => JSON.stringify(s) !== JSON.stringify(py.s[k]));
    console.log(f, 'sentences differ at', i, js.sentences[i], py.s[i]);
  }
  for (const k of Object.keys(py.c)) {
    const a = js.candidates[k].map(x => x.id).join(','), b = py.c[k].join(',');
    if (a !== b) { bad++; console.log(f, k, 'js', a, 'py', b); }
  }
  const H = J.headings(fs.readFileSync(path.join(R, f), 'utf8')); let nv = 0;
  for (const [k, want] of Object.entries(py.v)) {
    const [key, sid, val] = k.split('|'); const kind = J.TERMS.find(t => t[0] === key)[2]; const sent = js.sentences.find(x => x.id === sid);
    const got = J.verify(key, kind, JSON.parse(val), sent, J.contextFor(sent, js.sentences, H)); nv++;
    if (got[0] !== want[0] || got[1].replace('’', "'") !== want[1].replace('’', "'")) { bad++; if (bad < 6) console.log(f, 'verify differs', k, got, want); }
  }
  console.log(f, js.sentences.length, 'sentences,', nv, 'verify cases');
}
if (bad) { console.log('contract parity FAILED'); process.exit(1); }
console.log('contract parity ok:', files.length, 'contracts');
