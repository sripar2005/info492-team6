/* Delay check: what a time claim is worth under the contract, once the schedule analysis has said how many days
   the change really adds. Pure functions, no model. The days come from the time impact analysis in schedule.js
   (AACE 52R-06: insert the change's activities into the current schedule, rerun the critical path, compare finishes).

   delayCheck(contract, input) -> {
     extensionDays, paidDays: [low, high], rate: {value, low, high, methods}, cost: {low, high, point},
     ldExposure, flags: [{flag, severity, text, section}], steps: [audit lines]
   }
   input = { computedDays, claimedDays, onCriticalPath, causeParty: 'owner'|'architect'|'contractor'|'neither',
             compensable: null|true|false (null = follow the contract), concurrent: bool,
             claimedCost (extended general conditions in the proposal), claimedRate (optional, $/day in the proposal),
             sgcAlsoBilled (bool: the same field staff are also billed as SGC items in this proposal) } */
(function (root) {
  function r2(x) { return Math.round(x * 100) / 100; }
  function money(x) { return '$' + Number(r2(x)).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

  // Daily cost of extended general conditions. The contract's own daily rate wins; otherwise general conditions spread
  // over the contract time (the "time-related overhead" method). Other methods are shown for the range, not used alone.
  function rates(C, input) {
    var m = [];
    if (C.dailyDelayRate) m.push({ id: 'contract_rate', label: 'Daily rate stated in the contract', value: C.dailyDelayRate, section: C.sections && C.sections.sgcRate || '5.2' });
    if (C.sgcTotal && C.contractDays) m.push({ id: 'sgc_spread', label: 'General conditions ÷ contract days (' + money(C.sgcTotal) + ' ÷ ' + C.contractDays + ')', value: C.sgcTotal / C.contractDays });
    if (input.claimedRate) m.push({ id: 'claimed', label: 'Rate used in the proposal', value: input.claimedRate });
    // A rate stated in the contract governs; the spread method is only used when the contract states none.
    var basis = m.filter(function (x) { return x.id !== 'claimed'; }).slice(0, 1);
    var vals = basis.map(function (x) { return x.value; });
    return { value: basis.length ? basis[0].value : null, low: vals.length ? Math.min.apply(null, vals) : null, high: vals.length ? Math.max.apply(null, vals) : null, methods: m, used: basis[0] || null };
  }

  function delayCheck(C, input) {
    var steps = [], flags = [];
    var computed = Math.max(0, +input.computedDays || 0), claimed = +input.claimedDays || 0;
    var party = input.causeParty || 'neither';
    steps.push({ who: 'computed', text: 'Schedule analysis: the change moves the finish by ' + computed + ' calendar days' + (input.onCriticalPath === false ? ' (its work is not on the longest path).' : '.') });

    // 1. Time: how many days of extension the contract allows.
    var ext = computed;
    if (C.extensionRequiresCriticalPath && input.onCriticalPath === false) ext = 0;
    if (party === 'contractor') ext = 0;
    steps.push({ who: 'computed', text: party === 'contractor' ? 'Caused by the contractor: no extension.' : ext === computed ? 'Extension allowed: ' + ext + ' days.' : 'Extension allowed: 0 days (contract requires critical-path delay).' });

    // 2. Money: is this delay paid, or time only?
    var contractSaysPaid = (C.compensableCauses || []).indexOf(party) >= 0;
    var paid = input.compensable == null ? contractSaysPaid : !!input.compensable;
    var paidLow = 0, paidHigh = 0;
    if (paid && ext > 0) {
      if (input.concurrent) {
        if (C.concurrentDelay === 'apportioned') { paidLow = Math.floor(ext / 2); paidHigh = ext; }
        else if (C.concurrentDelay === 'not_stated') { paidLow = 0; paidHigh = ext; }
        else { paidLow = paidHigh = 0; }
      } else { paidLow = paidHigh = ext; }
    }
    steps.push({ who: input.compensable == null ? 'computed' : 'person', text: (input.compensable == null ? 'Contract: delays caused by ' + ((C.compensableCauses || []).join(' or ') || 'no one') + ' are paid. ' : 'Set by you: ') +
      (paid ? 'This delay is paid' : 'Time only, no money') + (input.concurrent ? '; concurrent delay → ' + ({ time_no_money: 'time, no money', no_time_no_money: 'no time, no money', apportioned: 'split', not_stated: 'contract silent, range shown' }[C.concurrentDelay] || C.concurrentDelay) : '') + '.' });
    if (input.concurrent && C.concurrentDelay === 'no_time_no_money') { ext = 0; paidLow = paidHigh = 0; }

    // 3. Rate and range.
    var R = rates(C, input), point = R.value != null ? r2(paidHigh * R.value) : null;
    var cost = { low: R.low != null ? r2(paidLow * R.low) : null, high: R.high != null ? r2(paidHigh * R.high) : null, point: paidLow === paidHigh ? point : null };
    if (R.used) steps.push({ who: 'computed', text: 'Rate: ' + R.used.label + ' = ' + money(R.used.value) + '/day.' + (R.methods.filter(function (m) { return m.id === 'sgc_spread'; })[0] && R.used.id !== 'sgc_spread' ? ' (For reference, general conditions ÷ contract days = ' + money(R.methods.filter(function (m) { return m.id === 'sgc_spread'; })[0].value) + '/day.)' : '') });
    else steps.push({ who: 'computed', text: 'No daily rate or general conditions total in the contract: cost not computed.' });

    // 4. Flags.
    if (claimed > computed) flags.push({ flag: 'DAYS_OVER_ANALYSIS', severity: 'fail', text: 'Claims ' + claimed + ' days; the schedule analysis shows ' + computed + '.', section: (C.sections && C.sections.time) || '6.4' });
    if (input.onCriticalPath === false && claimed > 0) flags.push({ flag: 'OFF_CRITICAL_PATH', severity: 'fail', text: 'The changed work has float; it does not move the finish.', section: '3.4' });
    if (input.claimedCost != null && cost.high != null && input.claimedCost > cost.high + 1) flags.push({ flag: 'DELAY_COST_OVER', severity: 'fail', text: 'Asks ' + money(input.claimedCost) + ' for extended general conditions; the contract supports up to ' + money(cost.high) + '.', section: '5.2' });
    if (input.claimedRate && R.value != null && input.claimedRate > R.value + 0.5) flags.push({ flag: 'RATE_OVER_CONTRACT', severity: 'fail', text: 'Uses ' + money(input.claimedRate) + '/day; the contract rate is ' + money(R.value) + '/day.', section: '5.2' });
    if (input.sgcAlsoBilled && input.claimedCost) flags.push({ flag: 'SGC_DOUBLE_CHARGE', severity: 'person', text: 'Field staff billed as general conditions items and also in the daily delay rate. Check they are not paid twice.', section: '5.2' });
    if (input.concurrent) flags.push({ flag: 'CONCURRENT', severity: 'person', text: 'Concurrent delay is a judgment call: who caused which days is for the owner’s rep to decide.', section: '6.5.6' });
    var ld = party === 'contractor' ? r2(computed * (C.ldPerDay || 0)) : 0;
    if (ld) steps.push({ who: 'computed', text: 'Contractor-caused delay: liquidated damages exposure ' + computed + ' × ' + money(C.ldPerDay) + ' = ' + money(ld) + '.' });

    return { extensionDays: ext, paidDays: [paidLow, paidHigh], paid: paid, rate: R, cost: cost, ldExposure: ld, flags: flags, steps: steps };
  }

  var api = { delayCheck: delayCheck, rates: rates };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.ClauseDelay = api;
})(this);
