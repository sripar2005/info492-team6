// Runs the database test's scenario (supabase/tests/visibility_test.sql) through assets/rules.js and the in-browser
// sample database (assets/demo-db.js), so the sample behaves the way the live database does.
// node tools/rules_test.js
var R = require('../assets/rules.js'), D = require('../assets/demo-db.js');
var n = 0;
function ok(cond, what) { if (!cond) { console.error('FAILED: ' + what); process.exit(1); } n++; }
function q(p) { return p.then(function (r) { if (r.error) throw new Error(r.error.message); return r.data; }); }

(async function () {
  var sb = D.make(), db = sb._db;
  var pid = await q(sb.rpc('start_project', { p_name: 'Test HS', p_type: 'gccm', p_company: 'Acme Builders', p_role: 'gc' }));
  var gc = db.project_companies[0].company_id;
  var own = await q(sb.rpc('add_sample_company', { p: pid, p_name: 'District', p_kind: 'owner' }));
  var arch = await q(sb.rpc('add_sample_company', { p: pid, p_name: 'Arch Co', p_kind: 'architect' }));
  var sa = await q(sb.rpc('add_sample_company', { p: pid, p_name: 'Sub A', p_kind: 'sub' }));
  var sbb = await q(sb.rpc('add_sample_company', { p: pid, p_name: 'Sub B', p_kind: 'sub' }));
  var role = { }; role[gc] = 'gc'; role[own] = 'owner'; role[arch] = 'architect'; role[sa] = 'sub'; role[sbb] = 'sub';

  var kp = (await q(sb.from('contracts').insert({ project_id: pid, kind: 'prime', up_company: own, down_company: gc, title: 'Prime' }).select().single())).id;
  var ka = (await q(sb.from('contracts').insert({ project_id: pid, kind: 'sub', up_company: gc, down_company: sa, parent_id: kp, title: 'Sub A subcontract' }).select().single())).id;
  var kb = (await q(sb.from('contracts').insert({ project_id: pid, kind: 'sub', up_company: gc, down_company: sbb, parent_id: kp, title: 'Sub B subcontract' }).select().single())).id;
  await q(sb.from('sov_lines').insert({ project_id: pid, contract_id: kp, description: 'Superintendent', amount: 100000, general_conditions: true, basis: 'time' }));
  await q(sb.from('documents').insert([{ project_id: pid, kind: 'rfi', title: 'RFI-1', visibility: 'project' },
    { project_id: pid, kind: 'contract', title: 'Sub A subcontract text', visibility: 'contract', contract_id: ka, author_company: gc },
    { project_id: pid, kind: 'other', title: 'GC internal estimate', visibility: 'company', author_company: gc }]));
  var K = {}; db.contracts.forEach(function (k) { K[k.id] = k; });

  var ra = (await q(sb.from('changes').insert({ project_id: pid, number: 'CR-A1', title: 'Extra drains', tier: 'sub_request', contract_id: ka, from_company: sa, to_company: gc, amount: 6567 }).select().single())).id;
  await q(sb.from('events').insert({ project_id: pid, change_id: ra, company_id: sa, kind: 'submit' }));
  ok(db.changes[0].status === 'with_gc', 'submit moves a sub request to the GC/CM');
  await q(sb.from('changes').insert({ project_id: pid, number: 'CR-B1', title: 'Draft only', tier: 'sub_request', contract_id: kb, from_company: sbb, to_company: gc, amount: 999 }));

  function seen(co, table) {
    var C = {}; db.changes.forEach(function (c) { C[c.id] = c; });
    if (table === 'changes') return db.changes.filter(function (c) { return R.seesChange(c, co, role[co]); });
    if (table === 'documents') return db.documents.filter(function (d) { return R.seesDoc(d, co, K); });
    if (table === 'contracts') return db.contracts.filter(function (k) { return R.seesContract(k, co); });
    if (table === 'sov') return db.sov_lines.filter(function (l) { return R.seesSov(l, co, K); });
    if (table === 'events') return db.events.filter(function (e) { return R.seesEvent(e, co, role[co], C); });
  }
  ok(seen(sa, 'changes').length === 1, 'Sub A sees only its own request');
  ok(seen(sa, 'documents').length === 2, 'Sub A sees the RFI and its own subcontract, not the GC estimate');
  ok(seen(sa, 'contracts').length === 2, 'Sub A sees the prime contract and its own subcontract');
  ok(seen(sa, 'sov').length === 0, 'Sub A cannot see the prime schedule of values');
  ok(seen(sbb, 'changes').length === 1 && seen(sbb, 'changes')[0].number === 'CR-B1', 'Sub B sees only its own draft');
  ok(seen(gc, 'changes').length === 1, 'GC/CM sees the submitted request, not Sub B’s draft');
  ok(seen(gc, 'documents').length === 3, 'GC/CM sees all three documents');
  ok(seen(gc, 'sov').length === 1, 'GC/CM sees the prime schedule of values');

  var cp = (await q(sb.from('changes').insert({ project_id: pid, number: 'CP-1', title: 'Extra drains', tier: 'proposal', contract_id: kp, from_company: gc, to_company: own, amount: 6895.35 }).select().single())).id;
  await q(sb.from('changes').update({ parent_id: cp }).eq('id', ra));
  await q(sb.from('events').insert({ project_id: pid, change_id: ra, company_id: gc, kind: 'bundle' }));
  await q(sb.from('events').insert({ project_id: pid, change_id: cp, company_id: gc, kind: 'draft', ai: { model: 'llama3.1:8b', citations: ['FR-33'] } }));
  var r1 = await sb.from('events').insert({ project_id: pid, change_id: cp, company_id: gc, kind: 'submit' });
  ok(r1.error && /checks/.test(r1.error.message), 'send is locked until the checks run');
  await q(sb.from('events').insert({ project_id: pid, change_id: cp, company_id: gc, kind: 'check', payload: { findings: 1 } }));
  var r2 = await sb.from('events').insert({ project_id: pid, change_id: cp, company_id: gc, kind: 'submit' });
  ok(r2.error && /explain/.test(r2.error.message), 'an open finding blocks sending');
  await q(sb.from('events').insert({ project_id: pid, change_id: cp, company_id: gc, kind: 'explain', body: 'NSS fee removed' }));
  await q(sb.from('events').insert({ project_id: pid, change_id: cp, company_id: gc, kind: 'submit' }));
  var CP = db.changes.filter(function (c) { return c.id === cp; })[0];
  ok(CP.status === 'with_architect' && CP.holder === arch, 'proposal goes to the architect');
  var r3 = await sb.from('events').update({ body: 'changed' }).eq('kind', 'submit');
  ok(r3.error, 'events cannot be edited');

  ok(seen(own, 'changes').length === 1 && seen(own, 'changes')[0].number === 'CP-1', 'Owner sees the proposal, not the sub request');
  ok(seen(own, 'documents').length === 1, 'Owner sees the RFI only');
  ok(seen(own, 'events').length === 4, 'Owner sees the proposal’s events only');
  ok(seen(arch, 'changes').length === 1, 'Architect sees the proposal');
  await q(sb.from('events').insert({ project_id: pid, change_id: cp, company_id: arch, kind: 'forward' }));
  ok(CP.status === 'with_owner' && CP.holder === own, 'architect forwards to the owner');
  await q(sb.from('events').insert({ project_id: pid, change_id: cp, company_id: own, kind: 'return', reason: 'missing_backup' }));
  ok(CP.status === 'with_architect' && CP.holder === arch, 'an owner return goes back one tier, to the architect');
  await q(sb.from('events').insert({ project_id: pid, change_id: cp, company_id: arch, kind: 'return', reason: 'missing_backup' }));
  ok(CP.status === 'returned' && CP.holder === gc, 'an architect return goes back to the GC/CM');
  await q(sb.from('events').insert({ project_id: pid, change_id: cp, company_id: gc, kind: 'confirm' }));
  var r4 = await sb.from('events').insert({ project_id: pid, change_id: cp, company_id: gc, kind: 'submit' });
  ok(r4.error, 'after a new confirmation, the checks must run again');
  await q(sb.from('events').insert({ project_id: pid, change_id: cp, company_id: gc, kind: 'check', payload: { findings: 0 } }));
  await q(sb.from('events').insert({ project_id: pid, change_id: cp, company_id: gc, kind: 'submit' }));
  await q(sb.from('events').insert({ project_id: pid, change_id: cp, company_id: arch, kind: 'forward' }));
  await q(sb.from('events').insert({ project_id: pid, change_id: cp, company_id: own, kind: 'approve' }));
  ok(db.changes.filter(function (c) { return c.id === ra; })[0].status === 'approved', 'owner approval flows down to Sub A’s request');

  var link = await q(sb.from('field_links').insert({ project_id: pid, company_id: sa }).select().single());
  await q(sb.rpc('submit_field', { p_token: link.token, p_body: 'Water coming in at the gym roof drain', p_name: 'Mo' }));
  var bad = await sb.rpc('submit_field', { p_token: 'nope', p_body: 'x x x' });
  ok(bad.error, 'a bad token is refused');
  ok(db.field_submissions.filter(function (s) { return R.seesFieldSubmission(s, sa); }).length === 1, 'Sub A sees the unverified submission');
  ok(db.field_submissions.filter(function (s) { return R.seesFieldSubmission(s, gc); }).length === 0, 'the GC/CM does not see it until Sub A confirms it');

  var g = R.flowdownGap(7, 7); ok(g.gap && g.margin === 0, 'equal notice windows are a flow-down gap');
  ok(!R.flowdownGap(7, 5).gap, 'a sub window two days shorter leaves the GC/CM time');
  console.log('rules ok: ' + n + ' checks (same scenario as the database test)');
})().catch(function (e) { console.error(e); process.exit(1); });
