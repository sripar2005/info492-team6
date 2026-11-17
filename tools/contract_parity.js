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
print(json.dumps({"s": s, "c": {k: [x["id"] for x in v] for k, v in c.items()}}))`], { cwd: R }).toString());
  const js = J.retrieve(fs.readFileSync(path.join(R, f), 'utf8'));
  if (JSON.stringify(js.sentences) !== JSON.stringify(py.s)) {
    bad++; const i = js.sentences.findIndex((s, k) => JSON.stringify(s) !== JSON.stringify(py.s[k]));
    console.log(f, 'sentences differ at', i, js.sentences[i], py.s[i]);
  }
  for (const k of Object.keys(py.c)) {
    const a = js.candidates[k].map(x => x.id).join(','), b = py.c[k].join(',');
    if (a !== b) { bad++; console.log(f, k, 'js', a, 'py', b); }
  }
  console.log(f, js.sentences.length, 'sentences');
}
if (bad) { console.log('contract parity FAILED'); process.exit(1); }
console.log('contract parity ok:', files.length, 'contracts');
