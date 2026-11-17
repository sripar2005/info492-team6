// node tools/delay_test.js — the delay-cost rules on the sample contract (daily rate $3,185; SGC $1,720,000 / 540 days).
const K = require('../assets/checks.js');
const D = require('../assets/delay.js');
const C = K.CONTRACT;
let bad = 0;
function eq(name, got, want) { const ok = JSON.stringify(got) === JSON.stringify(want); if (!ok) { bad++; console.log('FAIL', name, 'got', got, 'want', want); } }

let r = D.delayCheck(C, { computedDays: 10, claimedDays: 10, onCriticalPath: true, causeParty: 'owner', concurrent: false });
eq('owner paid', [r.extensionDays, r.paidDays, r.cost.point], [10, [10, 10], 31850]);
eq('contract rate governs', [r.cost.low, r.cost.high], [31850, 31850]);
r = D.delayCheck(Object.assign({}, C, { dailyDelayRate: null }), { computedDays: 10, claimedDays: 10, onCriticalPath: true, causeParty: 'owner' });
eq('no stated rate: general conditions spread', r.cost.point, Math.round(10 * 1720000 / 540 * 100) / 100);

r = D.delayCheck(C, { computedDays: 10, claimedDays: 14, onCriticalPath: true, causeParty: 'owner', concurrent: false, claimedCost: 14 * 3185 });
eq('padded days flagged', r.flags.map(f => f.flag), ['DAYS_OVER_ANALYSIS', 'DELAY_COST_OVER']);

r = D.delayCheck(C, { computedDays: 0, claimedDays: 6, onCriticalPath: false, causeParty: 'architect', concurrent: false });
eq('off critical path', [r.extensionDays, r.paidDays, r.flags.map(f => f.flag)], [0, [0, 0], ['DAYS_OVER_ANALYSIS', 'OFF_CRITICAL_PATH']]);

r = D.delayCheck(C, { computedDays: 8, claimedDays: 8, onCriticalPath: true, causeParty: 'owner', concurrent: true });
eq('concurrent: time, no money', [r.extensionDays, r.paidDays, r.cost.high], [8, [0, 0], 0]);

r = D.delayCheck(Object.assign({}, C, { concurrentDelay: 'apportioned' }), { computedDays: 8, claimedDays: 8, onCriticalPath: true, causeParty: 'owner', concurrent: true });
eq('concurrent: apportioned range', [r.paidDays, r.cost.low, r.cost.high], [[4, 8], 12740, 25480]);

r = D.delayCheck(C, { computedDays: 5, claimedDays: 5, onCriticalPath: true, causeParty: 'contractor', concurrent: false });
eq('contractor caused', [r.extensionDays, r.paidDays, r.ldExposure], [0, [0, 0], 12500]);

r = D.delayCheck(C, { computedDays: 5, claimedDays: 5, onCriticalPath: true, causeParty: 'neither', concurrent: false });
eq('neither party (e.g. weather): time only', [r.extensionDays, r.paidDays], [5, [0, 0]]);

r = D.delayCheck(C, { computedDays: 5, claimedDays: 5, onCriticalPath: true, causeParty: 'neither', compensable: true, concurrent: false });
eq('person overrides to paid', [r.paidDays, r.cost.point], [[5, 5], 15925]);

r = D.delayCheck(C, { computedDays: 5, claimedDays: 5, onCriticalPath: true, causeParty: 'owner', concurrent: false, claimedRate: 4100 });
eq('rate over contract', r.flags.map(f => f.flag), ['RATE_OVER_CONTRACT']);

if (bad) { console.log(bad, 'delay tests failed'); process.exit(1); }
console.log('delay tests ok');
