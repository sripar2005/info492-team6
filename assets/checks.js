/* ClauseStream contract checks, in the browser.
 *
 * A line-for-line port of demo3/calc.py, demo2/deadlines.py and demo3/rules.py so the check runs
 * with no server and no model. tools/parity.js runs this and the Python version on all 36 test
 * proposals and fails if any status, flag, dollar difference or route differs.
 *
 * Contract thresholds are for the synthetic GC/CM contract used throughout this project.
 */
(function (root) {
  'use strict';

  var CAUSES = ['RFI response', 'ASI', 'Submittal return', 'Owner direction', 'Architect direction', 'Concealed condition', 'Other event'];
  var NOTICE_RULE = { 'RFI response': '6.2(a)', 'ASI': '6.2(a)', 'Submittal return': '6.2(a)',
    'Owner direction': '6.2(b)', 'Architect direction': '6.2(b)', 'Concealed condition': '6.2(c)', 'Other event': '6.2(d)' };
  // The sample contract (demo1/data/synthetic_contract.md). A loaded contract replaces these numbers via fromTerms().
  var CONTRACT = {
    name: 'Sample GC/CM contract',
    note: 'Synthetic contract written for this project, modeled on the Webster School audit.',
    burdenPercent: 32, feePercent: 5, feeAllowedOn: ['CM direct costs', 'subcontractor quotes'],
    blueBookPercent: 75, markupOwn: 10, markupLower: 5, markupTotal: 15, approvalLimit: 250000,
    noticeDays: { '6.2(a)': 7, '6.2(b)': 7, '6.2(c)': 7, '6.2(d)': 14 },
    noticeByCause: { 'RFI response': 7, 'ASI': 7, 'Submittal return': 7, 'Owner direction': 7, 'Architect direction': 7, 'Concealed condition': 7, 'Other event': 14 },
    noticeSection: NOTICE_RULE,
    sections: { markup: '6.5.2', backup: '6.5.7', tieout: '6.5', fee: '6.5.3', burden: '5.4', equipment: '6.5.4', time: '6.4', concealed: '6.2(c)', approval: 'Exhibit D' },
    contractDays: 540, ldPerDay: 2500, dailyDelayRate: 3185, sgcTotal: 1720000,
    extensionRequiresCriticalPath: true, compensableCauses: ['owner', 'architect'], concurrentDelay: 'time_no_money'
  };
  // Contract terms (docs/demo4-spec.md section 3) -> the numbers the checks use. Missing terms keep the sample's value
  // and are listed in .defaulted so the page can say so.
  function fromTerms(name, terms) {
    var C = JSON.parse(JSON.stringify(CONTRACT)), d = [];
    function v(k) { var t = terms && terms[k]; return t && t.value != null && t.value !== '' ? t.value : null; }
    function set(prop, k, sec) { var x = v(k); if (x == null) { d.push(k); return; } C[prop] = x; if (sec && terms[k].section) C.sections[sec] = terms[k].section; }
    C.name = name || 'Loaded contract'; C.note = 'Loaded and confirmed by the user.';
    set('markupOwn', 'markup_own_pct', 'markup'); set('markupLower', 'markup_lower_pct'); set('markupTotal', 'markup_total_pct');
    set('feePercent', 'fee_pct', 'fee'); set('feeAllowedOn', 'fee_allowed_on'); set('burdenPercent', 'labor_burden_pct', 'burden');
    set('blueBookPercent', 'blue_book_pct', 'equipment'); set('approvalLimit', 'approval_limit', 'approval');
    set('contractDays', 'contract_days'); set('ldPerDay', 'liquidated_damages_per_day'); set('dailyDelayRate', 'daily_delay_rate');
    set('sgcTotal', 'sgc_total'); set('extensionRequiresCriticalPath', 'extension_requires_critical_path');
    set('compensableCauses', 'compensable_causes'); set('concurrentDelay', 'concurrent_delay');
    var nb = v('notice_days_by_cause');
    if (nb) { C.noticeByCause = Object.assign({}, C.noticeByCause, nb); var sec = terms.notice_days_by_cause.section || '';
      C.noticeSection = {}; CAUSES.forEach(function (c) { C.noticeSection[c] = sec || 'Notice'; }); }
    else d.push('notice_days_by_cause');
    C.defaulted = d;
    return C;
  }
  var FEE_BASE_FIELD = { 'NSS items': 'nss_items', 'SGC items': 'sgc_items', 'bond and insurance': 'bond_and_insurance',
    'B&O tax': 'bo_tax', 'permit fees': 'permit_fees', 'extended SGC (time)': 'extended_sgc_time' };
  var FORCE_ESCALATE = ['TIME_IMPACT', 'CONCEALED_CONDITION', 'OVER_AUTHORITY'];
  // Washington legal holidays 2020, observed (RCW 1.16.050). Same list as demo2/deadlines.py.
  var HOLIDAYS = ['2020-01-01', '2020-01-20', '2020-02-17', '2020-05-25', '2020-07-03', '2020-09-07',
    '2020-11-11', '2020-11-26', '2020-11-27', '2020-12-25',
    '2021-01-01', '2021-01-18', '2021-02-15', '2021-05-31', '2021-07-05', '2021-09-06', '2021-11-11', '2021-11-25', '2021-11-26', '2021-12-24'];
  var NOT_COMPUTED = ['Whether a cost is already covered by the Fee (Section 5.5)',
    'Whether the priced work is really a change from the drawings and specs',
    'Whether an equipment item belongs in SGC or NSS (Exhibits B and C)',
    'Whether hours, quantities and unit prices are reasonable'];

  // Python's round(x, n): correctly rounded on the exact binary value, half to even only on exact ties.
  function round(x, n) {
    n = n || 0;
    var r = Number(x.toFixed(n)), m = Math.pow(10, n), y = x * m;
    // An exact decimal tie is only possible when x is an odd multiple of 2^-(n+1) (multiplying by a power of 2 is exact).
    var t = x * Math.pow(2, n + 1);
    if (Number.isInteger(t) && Math.abs(t) % 2 === 1) r = (2 * Math.round(y / 2)) / m;
    return r === 0 ? 0 : r;
  }
  function pct(a, b) { return b ? round(100 * a / b, 2) : null; }
  function sum(a, f) { return a.reduce(function (s, x) { return s + f(x); }, 0); }
  function g(x) { return String(+x); } // like Python's :g for these values
  function py(x) { return Number.isInteger(x) ? x.toFixed(1) : String(x); } // like Python's str(float)
  function money(x) { var s = '$' + Math.abs(x).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); return x < 0 ? '-' + s : s; }

  function iso(d) { return d.toISOString().slice(0, 10); }
  function noticeDue(eventDate, rule) {
    if (!(rule in CONTRACT.noticeDays)) return null;
    return dueAfter(eventDate, CONTRACT.noticeDays[rule]);
  }
  // Calendar days after the event; a deadline on a weekend or holiday rolls to the next business day.
  function dueAfter(eventDate, days) {
    if (days == null) return null;
    var d = new Date(eventDate + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() + days);
    while (d.getUTCDay() === 0 || d.getUTCDay() === 6 || HOLIDAYS.indexOf(iso(d)) >= 0) d.setUTCDate(d.getUTCDate() + 1);
    return iso(d);
  }

  function sheet(cp, C) {
    C = C || CONTRACT;
    var out = { subcontractors: [], cm_lines: [], cover: {}, notice: {} };
    cp.subcontractor_quotes.forEach(function (q) {
      if (q.format === 'email text') {
        out.subcontractors.push({ firm: q.firm, format: 'email text', quote_total: q.quote_total });
        return;
      }
      var lines = q.lines || [], lower = q.lower_tier || [];
      var lineSum = lines.length ? round(sum(lines, function (l) { return l.amount; }), 2) : null;
      var lowSum = lower.length ? round(sum(lower, function (l) { return l.amount; }), 2) : 0;
      out.subcontractors.push({
        firm: q.firm,
        own_work_markup_percent: pct(q.markup_on_own, q.own_direct),
        lower_tier_markup_percent: pct(q.markup_on_lower_tier, q.lower_tier_total),
        total_markup_percent_of_direct: pct(q.markup_on_own + q.markup_on_lower_tier, q.own_direct + q.lower_tier_total),
        breakdown_attached: q.breakdown_attached != null ? !!q.breakdown_attached : lines.length > 0,
        lines_add_up_to_quote_direct: lineSum != null ? Math.abs(lineSum - q.own_direct) < 0.01 : null,
        lower_tier_adds_up: Math.abs(lowSum - q.lower_tier_total) < 0.01,
        tm_tags: (q.tm_tags || []).map(function (t) { return { tag: t.tag, signed_by_cm_superintendent: t.signed_by_cm_superintendent, signed_by_owner_rep: t.signed_by_owner_rep }; })
      });
    });
    cp.cm_lines.forEach(function (l) {
      var f = { desc: l.desc, kind: l.kind, amount: l.amount };
      if (l.kind === 'labor') f.burden_percent = round(100 * l.burden_rate, 1);
      if (l.kind === 'equipment' && 'blue_book_rate' in l) f.rate_as_percent_of_blue_book = pct(l.rate_charged, l.blue_book_rate);
      out.cm_lines.push(f);
    });
    var c = cp.cover_sheet;
    var parts = c.cm_direct_costs + c.subcontractor_quotes + c.fee + c.bond_and_insurance + c.bo_tax + c.permit_fees + c.nss_items + c.sgc_items + c.extended_sgc_time;
    out.cover = {
      sum_of_cover_lines: round(parts, 2), total_requested: c.total_requested,
      difference_total_minus_lines: round(c.total_requested - parts, 2),
      fee_rate_percent: round(100 * c.fee_rate, 2), fee_applied_to: c.fee_applied_to,
      extended_sgc_days: cp.time_impact_days, over_250000: c.total_requested > C.approvalLimit
    };
    var rule = (C.noticeSection || NOTICE_RULE)[cp.cause.type], due = dueAfter(cp.cause.event_date, C.noticeByCause[cp.cause.type]);
    out.notice = { cause_type: cp.cause.type, event_date: cp.cause.event_date, notice_date: cp.notice_date,
      notice_rule_for_cause_type: rule, notice_due: due, notice_on_time: cp.notice_date <= due };
    return out;
  }

  function checksheet(cp, contract) {
    var C = contract || CONTRACT, X = C.sections, s = sheet(cp, C), rows = [];
    function row(check, section, status, contract, proposal, flag, difference, note, firm) {
      rows.push({ check: check, section: section, status: status, contract: contract, proposal: proposal,
        difference: difference == null ? null : difference, flag: flag || null, note: note || null, firm: firm || null });
    }
    cp.subcontractor_quotes.forEach(function (raw, i) {
      var q = s.subcontractors[i], firm = q.firm;
      if (q.format === 'email text') {
        row(firm + ': markup, breakdown and totals', X.markup + ', ' + X.backup, 'not_checked', g(C.markupOwn) + '% own work, ' + g(C.markupLower) + '% lower tier, ' + g(C.markupTotal) + '% total; itemized breakdown',
          'Quote arrived as email text', null, null, 'Not read by the calculator. A person or an agent has to read it.', firm);
        return;
      }
      var own = q.own_work_markup_percent, low = q.lower_tier_markup_percent, tot = q.total_markup_percent_of_direct, over = [], excess = 0;
      if ((own || 0) > C.markupOwn) { over.push(py(own) + '% on own work'); excess += raw.markup_on_own - raw.own_direct * C.markupOwn / 100; }
      if ((low || 0) > C.markupLower) { over.push(py(low) + '% on lower tier'); excess += raw.markup_on_lower_tier - raw.lower_tier_total * C.markupLower / 100; }
      if ((tot || 0) > C.markupTotal && !over.length) over.push(py(tot) + '% total');
      var shown = py(own) + '% on own work' + (low != null ? ', ' + py(low) + '% on lower tier' : '');
      row(firm + ': markup', X.markup, over.length ? 'fail' : 'pass', g(C.markupOwn) + '% own work, ' + g(C.markupLower) + '% lower tier, ' + g(C.markupTotal) + '% total',
        over.length ? over.join(', ') : shown, over.length ? 'SUB_MARKUP' : null, excess > 0 ? round(excess, 2) : null, null, firm);
      row(firm + ': itemized breakdown', X.backup, q.breakdown_attached ? 'pass' : 'fail', 'Breakdown of labor, material and equipment attached',
        q.breakdown_attached ? 'Attached' : 'Lump sum, no breakdown', q.breakdown_attached ? null : 'MISSING_BACKUP', null, null, firm);
      if (q.tm_tags.length) {
        var bad = q.tm_tags.filter(function (t) { return !(t.signed_by_cm_superintendent && t.signed_by_owner_rep); }).map(function (t) { return t.tag; });
        row(firm + ': T&M tags signed', X.backup, bad.length ? 'fail' : 'pass', "Signed by CM superintendent and Owner's Representative",
          bad.length ? 'Unsigned: ' + bad.join(', ') : q.tm_tags.length + ' of ' + q.tm_tags.length + ' signed', bad.length ? 'MISSING_BACKUP' : null, null, null, firm);
      }
      var adds = q.lines_add_up_to_quote_direct !== false && q.lower_tier_adds_up;
      if (q.breakdown_attached && q.lines_add_up_to_quote_direct !== null)
        row(firm + ': lines add up', X.tieout, adds ? 'pass' : 'fail', 'Lines sum to the quoted direct cost', adds ? 'They do' : 'They do not', adds ? null : 'TIEOUT', null, null, firm);
    });
    var c = s.cover, cov = cp.cover_sheet, diff = c.difference_total_minus_lines;
    row('Cover sheet ties out', X.tieout, Math.abs(diff) > 1 ? 'fail' : 'pass', 'Lines sum to ' + money(c.sum_of_cover_lines), 'Total requested ' + money(c.total_requested),
      Math.abs(diff) > 1 ? 'TIEOUT' : null, Math.abs(diff) > 1 ? diff : null);
    var base = cov.cm_direct_costs + cov.subcontractor_quotes, rateOk = c.fee_rate_percent === C.feePercent;
    row('Fee rate', X.fee, rateOk ? 'pass' : 'fail', g(C.feePercent) + '%', g(c.fee_rate_percent) + '%', rateOk ? null : 'FEE_RATE',
      rateOk ? null : round((c.fee_rate_percent - C.feePercent) / 100 * base, 2));
    var excluded = c.fee_applied_to.filter(function (p) { return C.feeAllowedOn.indexOf(p) < 0; });
    var feeOnExcl = round(sum(excluded, function (p) { return cov[FEE_BASE_FIELD[p]] || 0; }) * cov.fee_rate, 2);
    row('Fee base', X.fee, excluded.length ? 'fail' : 'pass', 'Fee on ' + C.feeAllowedOn.join(' and ') + ' only',
      excluded.length ? 'Fee also taken on ' + excluded.join(', ') : 'Fee on ' + C.feeAllowedOn.join(' and '),
      excluded.length ? 'FEE_ON_EXCLUDED' : null, excluded.length && feeOnExcl ? feeOnExcl : null);
    cp.cm_lines.forEach(function (raw, i) {
      var l = s.cm_lines[i];
      if (l.burden_percent != null) {
        var ok = l.burden_percent === C.burdenPercent;
        row('Labor burden: ' + l.desc, X.burden, ok ? 'pass' : 'fail', g(C.burdenPercent) + '%', g(l.burden_percent) + '%', ok ? null : 'LABOR_BURDEN',
          ok ? null : round(raw.hours * raw.wage * (l.burden_percent - C.burdenPercent) / 100, 2));
      }
      if (l.rate_as_percent_of_blue_book != null) {
        var ok2 = l.rate_as_percent_of_blue_book <= C.blueBookPercent;
        row('Owned equipment rate: ' + l.desc, X.equipment, ok2 ? 'pass' : 'fail', 'No more than ' + g(C.blueBookPercent) + '% of Blue Book',
          g(l.rate_as_percent_of_blue_book) + '% of Blue Book', ok2 ? null : 'EQUIPMENT');
      }
    });
    var n = s.notice;
    row('Notice on time', n.notice_rule_for_cause_type, n.notice_on_time ? 'pass' : 'fail', 'Due ' + n.notice_due + ' (' + n.cause_type + ' on ' + n.event_date + ')',
      'Given ' + n.notice_date, n.notice_on_time ? null : 'LATE_NOTICE');
    var days = c.extended_sgc_days;
    row('Time claim', X.time, days > 0 ? 'person' : 'pass', 'A claim for time is decided by a person', days > 0 ? days + ' days claimed' : 'No time claimed', days > 0 ? 'TIME_IMPACT' : null);
    var concealed = cp.cause.type === 'Concealed condition';
    row('Site condition', X.concealed, concealed ? 'person' : 'pass', 'Entitlement for a concealed condition is decided by a person',
      concealed ? 'Cause is a concealed condition' : 'Cause: ' + cp.cause.type, concealed ? 'CONCEALED_CONDITION' : null);
    row('Approval limit', X.approval, c.over_250000 ? 'person' : 'pass', "Owner's Representative may approve up to " + money(C.approvalLimit),
      'Total requested ' + money(c.total_requested), c.over_250000 ? 'OVER_AUTHORITY' : null);

    var counts = { pass: 0, fail: 0, person: 0, not_checked: 0 }, at = 0, types = {};
    rows.forEach(function (r) { counts[r.status]++; if (r.status === 'fail' && r.difference > 0) at += r.difference; if (r.flag) types[r.flag] = 1; });
    var route = FORCE_ESCALATE.some(function (t) { return types[t]; }) ? 'ESCALATE' : Object.keys(types).length ? 'RETURN' : 'APPROVE';
    return { id: cp.id, title: cp.title, total_requested: cov.total_requested, route: route, counts: counts,
      dollars_at_issue: round(at, 2), rows: rows, not_computed: NOT_COMPUTED, notice: n };
  }

  /* ---------- Plain-English findings, worded for the person reading ---------- */
  var ROLE = {
    sub: { label: 'Subcontractor', q: 'Will your quote get sent back?', send: 'before you send it to the GC/CM' },
    gc: { label: 'GC/CM', q: 'Will your change proposal get sent back?', send: 'before you send it to the owner' },
    architect: { label: 'Architect', q: 'Is this change proposal priced the way the contract allows?', send: 'before you sign off on scope' },
    owner: { label: "Owner's rep", q: 'Is this change proposal priced the way the contract allows?', send: 'before you approve it' }
  };
  function plain(r, role, C) {
    var out = plain0(r, role, C || CONTRACT);
    out.why = out.why.replace(/(\d+)\.0%/g, '$1%'); out.title = out.title.replace(/(\d+)\.0%/g, '$1%');
    return out;
  }
  function plain0(r, role, C) {
    var owner = role === 'owner' || role === 'architect', amt = r.difference > 0 ? r.difference : null, f = r.firm ? r.firm + "'s" : 'The';
    switch (r.flag) {
      case 'SUB_MARKUP': return { title: f + ' markup is over the limit.', why: 'The contract allows ' + g(C.markupOwn) + '% on their own work, ' + g(C.markupLower) + '% on lower-tier subs, ' + g(C.markupTotal) + '% total. This quote has ' + r.proposal + '.', amt: amt };
      case 'MISSING_BACKUP': return r.check.indexOf('T&M') >= 0
        ? { title: 'Time-and-material tags are missing signatures.', why: r.proposal + '. Each tag needs the CM superintendent and the owner\'s rep.', amt: null }
        : { title: (r.firm || 'A subcontractor') + "'s quote has no breakdown.", why: 'It is a lump sum. The contract needs labor, material and equipment itemized.', amt: null };
      case 'TIEOUT': return r.check.indexOf('Cover') === 0
        ? { title: "The cover sheet total doesn't add up.", why: 'The lines add to ' + r.contract.replace('Lines sum to ', '') + ' but the total says ' + r.proposal.replace('Total requested ', '') + '.', amt: r.difference != null ? Math.abs(r.difference) : null }
        : { title: (r.firm || 'A') + "'s quote lines don't add up to its total.", why: 'The itemized lines and the quoted cost differ.', amt: null };
      case 'FEE_RATE': return { title: 'The CM fee is at the wrong rate.', why: 'The contract fee is ' + r.contract + '. This proposal uses ' + r.proposal + '.', amt: amt };
      case 'FEE_ON_EXCLUDED': return { title: 'The CM fee was charged on items the contract excludes.', why: 'The fee is allowed only on ' + C.feeAllowedOn.map(function (p) { return p === 'CM direct costs' ? 'the CM\'s own work' : p; }).join(' and ') + '. ' + r.proposal.replace('Fee also taken on', 'It was also taken on') + '.', amt: amt };
      case 'LABOR_BURDEN': return { title: 'Labor burden is above the contract rate.', why: r.check.replace('Labor burden: ', '') + ' is billed with ' + r.proposal + ' burden. The contract rate is ' + r.contract + '.', amt: amt };
      case 'EQUIPMENT': return { title: 'Owned equipment is billed above the allowed rate.', why: r.check.replace('Owned equipment rate: ', '') + ' is at ' + r.proposal + '. The limit is ' + g(C.blueBookPercent) + '%.', amt: null };
      case 'LATE_NOTICE': return { title: 'Notice was given late.', why: 'It was ' + r.contract.replace('Due ', 'due ').replace(/ \(.*\)/, '') + '; it was ' + r.proposal.replace('Given ', 'given ') + '. Costs before notice may not be owed.', amt: null };
      case 'TIME_IMPACT': return { title: 'A time extension is being claimed.', why: r.proposal + '. ' + (owner ? 'That is your decision, not the checklist\'s.' : 'The owner\'s rep decides this, so expect a conversation.'), amt: null };
      case 'CONCEALED_CONDITION': return { title: 'A hidden site condition goes to the owner\'s rep.', why: owner ? 'Whether it is owed is your call. Nothing here to recompute.' : 'Nothing to fix, but expect them to decide whether it is owed.', amt: null };
      case 'OVER_AUTHORITY': return { title: 'It is over the ' + money(C.approvalLimit).replace('.00', '') + ' approval limit.', why: owner ? 'It needs approval above the owner\'s representative.' : 'It will need approval above the owner\'s representative, which takes longer.', amt: null };
    }
    if (r.status === 'not_checked') return { title: (r.firm || 'A') + "'s quote came as email text.", why: 'We don\'t read free text, so its markup and breakdown are not checked. Read it yourself.', amt: null };
    return { title: r.check, why: r.proposal, amt: amt };
  }
  function verdict(cs, role) {
    var fails = cs.rows.filter(function (r) { return r.status === 'fail'; }).length;
    var person = cs.rows.filter(function (r) { return r.status === 'person'; }).length;
    var owner = role === 'owner' || role === 'architect';
    if (fails) return { tone: 'fail', head: owner ? fails + ' pricing ' + (fails === 1 ? 'problem' : 'problems') : fails + (fails === 1 ? ' thing' : ' things') + ' will get this sent back',
      sub: owner ? 'Return it with these notes.' : 'Fix ' + (fails === 1 ? 'it' : 'them') + ' ' + ROLE[role].send + '.' };
    if (person) return { tone: 'person', head: owner ? 'Pricing checks pass. One decision is yours.' : 'Ready to send, with one decision for the owner',
      sub: owner ? 'The arithmetic is right. A person still has to decide what is owed.' : 'The arithmetic is right. Expect the owner\'s rep to rule on the item below.' };
    return { tone: 'ok', head: owner ? 'Priced the way the contract allows' : 'Ready to send', sub: owner ? 'Every computed check passes. Scope and reasonableness are still yours to judge.' : 'Every computed check passes.' };
  }

  /* ---------- The editable form: a flat, plain record that round-trips to the case format ---------- */
  function idx(cp) { return cp.cm_lines.map(function (l, i) { return { l: l, i: i }; }); }
  function toForm(cp) {
    var c = cp.cover_sheet;
    return {
      id: cp.id || '', title: cp.title || '', cause: cp.cause.type, cause_ref: cp.cause.reference || '', event_date: cp.cause.event_date,
      notice_date: cp.notice_date, time_days: cp.time_impact_days || 0,
      subs: cp.subcontractor_quotes.map(function (q) {
        if (q.format === 'email text') return { firm: q.firm, trade: q.trade || '', email_only: true, quote_total: q.quote_total, text: q.text || '' };
        return { firm: q.firm, trade: q.trade || '', email_only: false, own_cost: q.own_direct, own_markup_pct: q.own_direct ? round(100 * q.markup_on_own / q.own_direct, 2) : 0,
          lower_cost: q.lower_tier_total, lower_markup_pct: q.lower_tier_total ? round(100 * q.markup_on_lower_tier / q.lower_tier_total, 2) : 0,
          breakdown: (q.lines || []).length > 0, _lines: q.lines || [], _lower: q.lower_tier || [], _stated: { own: q.markup_on_own, low: q.markup_on_lower_tier, total: q.quote_total },
          tm_tags: (q.tm_tags || []).map(function (t) { return { tag: t.tag, date: t.date, signed: !!(t.signed_by_cm_superintendent && t.signed_by_owner_rep), _s: t }; }) };
      }),
      cm_direct: c.cm_direct_costs,
      labor: idx(cp).filter(function (x) { return x.l.kind === 'labor'; }).map(function (x) { var l = x.l; return { desc: l.desc, hours: l.hours, wage: l.wage, burden_pct: round(100 * l.burden_rate, 1), _l: l, _i: x.i }; }),
      equipment: idx(cp).filter(function (x) { return x.l.kind === 'equipment' && 'blue_book_rate' in x.l; }).map(function (x) { var l = x.l; return { desc: l.desc, rate: l.rate_charged, blue_book: l.blue_book_rate, hours: l.hours_used, _l: l, _i: x.i }; }),
      _other_lines: idx(cp).filter(function (x) { return !(x.l.kind === 'labor' || (x.l.kind === 'equipment' && 'blue_book_rate' in x.l)); }).map(function (x) { return Object.assign({}, x.l, { _i: x.i }); }),
      nss: c.nss_items, sgc: c.sgc_items, bond: c.bond_and_insurance, bo: c.bo_tax, permits: c.permit_fees, ext_sgc: c.extended_sgc_time,
      fee_pct: round(100 * c.fee_rate, 2), fee_on: c.fee_applied_to.slice(), fee_amount: c.fee, total: c.total_requested,
      sub_total: c.subcontractor_quotes, _auto: false
    };
  }
  var FEE_ON = [['CM direct costs', 'cm_direct'], ['subcontractor quotes', 'sub_total'], ['NSS items', 'nss'], ['SGC items', 'sgc'],
    ['bond and insurance', 'bond'], ['B&O tax', 'bo'], ['permit fees', 'permits'], ['extended SGC (time)', 'ext_sgc']];
  function n(x) { x = +x; return isFinite(x) ? x : 0; }
  function subTotal(s) {
    if (s.email_only) return n(s.quote_total);
    var own = n(s.own_cost), low = n(s.lower_cost);
    return round(own + own * n(s.own_markup_pct) / 100 + low + low * n(s.lower_markup_pct) / 100, 2);
  }
  // Recompute the totals a person would expect when they edit one number.
  function recompute(f) {
    f.sub_total = round(sum(f.subs, subTotal), 2);
    var base = sum(FEE_ON, function (p) { return f.fee_on.indexOf(p[0]) >= 0 ? n(f[p[1]]) : 0; });
    f.fee_amount = round(base * n(f.fee_pct) / 100, 2);
    f.total = round(n(f.cm_direct) + f.sub_total + f.fee_amount + n(f.bond) + n(f.bo) + n(f.permits) + n(f.nss) + n(f.sgc) + n(f.ext_sgc), 2);
    return f;
  }
  // Keep the CM lines in their original order so a proposal round-trips exactly; new lines go last.
  // Uses stored indexes, not object identity, so it still works after the form is saved and reloaded.
  function orderLines(f, built) {
    var src = all(f);
    return built.map(function (b, i) { return { b: b, k: src[i] && src[i]._i != null ? src[i]._i : 1e9 + i }; })
      .sort(function (a, b) { return a.k - b.k; })
      .map(function (x) { var o = Object.assign({}, x.b); delete o._i; return o; });
  }
  function all(f) { return f.labor.concat(f.equipment, f._other_lines || []); }
  function toCase(f) {
    return {
      id: f.id || 'CHECK', title: f.title || 'Change proposal',
      cause: { type: f.cause, reference: f.cause_ref || '', event_date: f.event_date },
      notice_date: f.notice_date, time_impact_days: n(f.time_days),
      subcontractor_quotes: f.subs.map(function (s) {
        if (s.email_only) return { firm: s.firm || 'Subcontractor', trade: s.trade || '', format: 'email text', quote_total: n(s.quote_total), text: s.text || '' };
        var own = n(s.own_cost), low = n(s.lower_cost), st = s._stated || {};
        var mOwn = st.own != null && Math.abs(round(100 * st.own / (own || 1), 2) - n(s.own_markup_pct)) < 1e-9 ? st.own : round(own * n(s.own_markup_pct) / 100, 2);
        var mLow = st.low != null && Math.abs((low ? round(100 * st.low / low, 2) : 0) - n(s.lower_markup_pct)) < 1e-9 ? st.low : round(low * n(s.lower_markup_pct) / 100, 2);
        return { firm: s.firm || 'Subcontractor', trade: s.trade || '', own_direct: own, markup_on_own: mOwn, lower_tier_total: low, markup_on_lower_tier: mLow,
          quote_total: round(own + mOwn + low + mLow, 2), lines: s.breakdown ? (s._lines && s._lines.length ? s._lines : []) : [],
          breakdown_attached: !!s.breakdown, lower_tier: s._lower || [],
          tm_tags: (s.tm_tags || []).map(function (t) { return t._s && t.signed === !!(t._s.signed_by_cm_superintendent && t._s.signed_by_owner_rep) ? t._s
            : { tag: t.tag, date: t.date || '', signed_by_cm_superintendent: !!t.signed, signed_by_owner_rep: !!t.signed }; }) };
      }),
      cm_lines: orderLines(f, f.labor.map(function (l) { var b = n(l.burden_pct) / 100; return Object.assign({}, l._l || {}, { kind: 'labor', desc: l.desc, hours: n(l.hours), wage: n(l.wage), burden_rate: (l._l && round(100 * l._l.burden_rate, 1) === n(l.burden_pct)) ? l._l.burden_rate : b, amount: round(n(l.hours) * n(l.wage) * (1 + b), 2) }); })
        .concat(f.equipment.map(function (e) { return Object.assign({}, e._l || {}, { kind: 'equipment', owned_by_cm: true, desc: e.desc, rate_charged: n(e.rate), blue_book_rate: n(e.blue_book), hours_used: n(e.hours), amount: round(n(e.rate) * n(e.hours), 2) }); }))
        .concat((f._other_lines || []).map(function (l) { return Object.assign({}, l); }))),
      cover_sheet: { cm_direct_costs: n(f.cm_direct), subcontractor_quotes: n(f.sub_total), fee_rate: n(f.fee_pct) / 100, fee_applied_to: f.fee_on.slice(), fee: n(f.fee_amount),
        bond_and_insurance: n(f.bond), bo_tax: n(f.bo), permit_fees: n(f.permits), nss_items: n(f.nss), sgc_items: n(f.sgc), extended_sgc_time: n(f.ext_sgc), total_requested: n(f.total) }
    };
  }

  var api = { CONTRACT: CONTRACT, CAUSES: CAUSES, fromTerms: fromTerms, dueAfter: dueAfter, NOTICE_RULE: NOTICE_RULE, FEE_ON: FEE_ON, ROLE: ROLE, noticeDue: noticeDue, sheet: sheet, checksheet: checksheet,
    plain: plain, verdict: verdict, toForm: toForm, toCase: toCase, recompute: recompute, subTotal: subTotal, money: money, round: round };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.ClauseChecks = api;
})(this);
