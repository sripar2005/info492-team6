/* Who sees what, and how a change moves. The same rules the database enforces (supabase/migrations/0003_platform.sql),
   written once more in JavaScript for the in-browser sample and for "Viewing as" on a synthetic project.
   tools/rules_test.js runs the database test's scenario through these functions so the two stay in step.

   A row here has the same fields as the database row. `co` is the company you're viewing as; `role` is its role on the project. */
(function (root) {
  'use strict';

  // ---------- visibility ----------
  function seesChange(c, co, role) {
    if (!c) return false;
    if (c.from_company === co) return true;
    if (c.status !== 'draft' && c.to_company === co) return true;
    return c.tier === 'proposal' && c.status !== 'draft' && (role === 'owner' || role === 'architect');
  }
  function seesContract(k, co) { return !!k && (k.kind === 'prime' || k.up_company === co || k.down_company === co); }
  function partyTo(k, co) { return !!k && (k.up_company === co || k.down_company === co); }
  function seesDoc(d, co, contractsById) {
    if (!d) return false;
    if (d.visibility === 'project') return true;
    if (d.visibility === 'company') return d.author_company === co;
    if (d.visibility === 'contract') return partyTo(contractsById[d.contract_id], co);
    return false;
  }
  function seesSov(line, co, contractsById) { return partyTo(contractsById[line.contract_id], co); }
  function seesEvent(e, co, role, changesById) { return !e.change_id || seesChange(changesById[e.change_id], co, role); }
  function seesFieldSubmission(s, co) { return s.company_id === co; }

  // ---------- moving a change ----------
  // Before an event is added: a GC/CM proposal can't go up until the checks have run since the last draft or
  // confirmation, and every finding is fixed (a fresh check with none) or explained.
  function sendBlocker(change, events) {
    if (change.tier !== 'proposal') return null;
    var mine = events.filter(function (e) { return e.change_id === change.id; }).sort(function (a, b) { return a.id - b.id; });
    var lastDraft = 0, lastCheck = null, explained = false;
    mine.forEach(function (e) {
      if (e.kind === 'draft' || e.kind === 'confirm') { lastDraft = e.id; lastCheck = null; explained = false; }
      if (e.kind === 'check' && e.id > lastDraft) { lastCheck = e; explained = false; }
      if (e.kind === 'explain' && lastCheck && e.id > lastCheck.id) explained = true;
    });
    if (!lastCheck) return 'Run the contract checks before sending this up.';
    if (+((lastCheck.payload || {}).findings || 0) > 0 && !explained) return 'Fix or explain each finding before sending.';
    return null;
  }
  // After an event: the new status and holder. `arch` is the architect's company on the project, or null.
  function advance(change, kind, arch) {
    var s = change.status, h = change.holder;
    if (change.tier === 'sub_request') {
      if (kind === 'submit') { s = 'with_gc'; h = change.to_company; }
      else if (kind === 'return') { s = 'returned'; h = change.from_company; }
      else if (kind === 'bundle') { s = 'bundled'; }
      return { status: s, holder: h };
    }
    if (kind === 'submit') { s = arch ? 'with_architect' : 'with_owner'; h = arch || change.to_company; }
    else if (kind === 'forward') { s = 'with_owner'; h = change.to_company; }
    else if (kind === 'return' && change.status === 'with_owner' && arch) { s = 'with_architect'; h = arch; }
    else if (kind === 'return') { s = 'returned'; h = change.from_company; }
    else if (kind === 'approve') s = 'approved';
    else if (kind === 'reject') s = 'rejected';
    return { status: s, holder: h };
  }
  // An owner decision flows down to every sub request in the proposal.
  function flowDown(kind) { return kind === 'approve' ? 'approved' : kind === 'reject' ? 'rejected' : null; }

  // ---------- deadlines and flow-down ----------
  function addDays(iso, n) { var d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }
  function daysBetween(a, b) { return Math.round((Date.parse(b + 'T00:00:00Z') - Date.parse(a + 'T00:00:00Z')) / 864e5); }
  // A subcontract's notice window must leave the GC/CM time to pass notice up under the prime contract.
  // margin = prime window - sub window. A margin under `minDays` is a gap.
  function flowdownGap(primeDays, subDays, minDays) {
    if (primeDays == null || subDays == null) return null;
    var margin = primeDays - subDays, need = minDays == null ? 1 : minDays;
    return { margin: margin, gap: margin < need, short: Math.max(0, need - margin) };
  }

  // Cost per day of delay: the time-based general conditions in the schedule of values, spread over the contract time,
  // next to the rate the contract states. The stated rate governs when there is one.
  function costPerDay(lines, stated, contractDays) {
    var gc = (lines || []).filter(function (l) { return l.general_conditions && (l.basis === 'time' || !l.basis); });
    var total = gc.reduce(function (s, l) { return s + (+l.amount || 0); }, 0), spread = total && contractDays ? total / contractDays : null;
    return { value: stated != null ? +stated : spread, stated: stated != null ? +stated : null, spread: spread, total: total, days: contractDays, lines: gc };
  }
  // Do a change's sub requests add up to what the proposal carries for them?
  function rollup(requests, carried) {
    var sum = (requests || []).reduce(function (s, r) { return s + (+r.amount || 0); }, 0);
    return { total: Math.round(sum * 100) / 100, carried: carried, match: carried == null || Math.abs(sum - carried) <= 0.5 };
  }
  var api = { seesChange: seesChange, seesContract: seesContract, seesDoc: seesDoc, seesSov: seesSov, seesEvent: seesEvent, seesFieldSubmission: seesFieldSubmission,
    partyTo: partyTo, sendBlocker: sendBlocker, advance: advance, flowDown: flowDown, flowdownGap: flowdownGap, costPerDay: costPerDay, rollup: rollup, addDays: addDays, daysBetween: daysBetween };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.CSRules = api;
})(this);
