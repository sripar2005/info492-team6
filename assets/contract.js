/* Contract reading helpers, browser port of demo4/contract_extract.py (no model).
   Splits a contract into numbered sentences with their sections, finds the few sentences that could state each term,
   and checks that a chosen sentence actually contains the value. tools/contract_parity.js keeps this in step with Python. */
(function (root) {
  var FEE_ON = ['CM direct costs', 'subcontractor quotes', 'NSS items', 'SGC items', 'bond and insurance', 'B&O tax', 'permit fees', 'extended SGC (time)'];
  var FEE_WORDS = { 'CM direct costs': ['cost of the work', 'cm direct', 'direct cost', "cm's own"], 'subcontractor quotes': ['subcontract'],
    'NSS items': ['nss', 'non-standard'], 'SGC items': ['sgc', 'general conditions'], 'bond and insurance': ['bond', 'insurance'],
    'B&O tax': ['b&o', 'business and occupation'], 'permit fees': ['permit'], 'extended SGC (time)': ['extended'] };
  // key, plain label, kind, retrieval keywords, group  (same order and words as TERMS in contract_extract.py)
  var TERMS = [
    ['markup_own_pct', 'Sub markup on its own work', 'pct', ['markup', 'own work', 'subcontractor', 'self-performed'], 'Pricing'],
    ['markup_lower_pct', 'Sub markup on lower-tier work', 'pct', ['markup', 'lower-tier', 'lower tier', 'sub-subcontractor'], 'Pricing'],
    ['markup_total_pct', 'Total sub markup cap', 'pct', ['markup', 'total', 'combined', 'in no event', 'aggregate'], 'Pricing'],
    ['fee_pct', 'CM fee', 'pct', ['fee', 'percent', '%'], 'Pricing'],
    ['fee_allowed_on', 'Fee allowed on', 'fee_on', ['fee', 'may add', 'direct cost', 'markups', 'no fee', 'of a change'], 'Pricing'],
    ['labor_burden_pct', 'Labor burden', 'pct', ['burden', 'labor', 'payroll', 'fringe'], 'Pricing'],
    ['blue_book_pct', 'Owned equipment rate (of Blue Book)', 'pct', ['blue book', 'equipment', 'rental rate'], 'Pricing'],
    ['approval_limit', 'Owner’s rep approval limit', 'money', ['approve', 'authority', 'representative', 'up to', 'limit'], 'Pricing'],
    ['notice_days_standard', 'Notice window: RFI answers, directions, site conditions', 'days', ['notice', 'days', 'rfi', 'direction', 'concealed', 'receives', 'response', 'asi', 'submittal'], 'Notice'],
    ['notice_days_other', 'Notice window: any other event', 'days', ['notice', 'days', 'other event', 'should have known', 'any other'], 'Notice'],
    ['contract_days', 'Contract time', 'days', ['substantial completion', 'days', 'notice to proceed', 'contract time'], 'Time'],
    ['liquidated_damages_per_day', 'Liquidated damages per day', 'money', ['liquidated', 'each day', 'per day', 'damages'], 'Time'],
    ['daily_delay_rate', 'Daily rate for extended general conditions', 'money', ['daily rate', 'per day', 'extension', 'general conditions', 'extended'], 'Time'],
    ['sgc_total', 'General conditions total', 'money', ['general conditions', 'sgc', 'is $', 'lump sum'], 'Time'],
    ['extension_requires_critical_path', 'Extensions only for critical-path delays', 'bool', ['critical path', 'extension', 'time extension', 'extended only'], 'Time'],
    ['compensable_causes', 'Delays that are paid, not just extended', 'parties', ['compensated', 'compensable', 'caused by', 'owner', 'architect'], 'Time'],
    ['concurrent_delay', 'Concurrent delay', 'concurrent', ['concurrent'], 'Time']
  ];
  var CONCURRENT = [['time_no_money', 'Time, no money'], ['no_time_no_money', 'No time, no money'], ['apportioned', 'Split between the parties'], ['not_stated', 'Not stated']];
  var CAUSES = ['RFI response', 'ASI', 'Submittal return', 'Owner direction', 'Architect direction', 'Concealed condition', 'Other event'];

  function sentences(text) {
    var out = [], sec = '', parent = '';
    String(text).split(/\r?\n/).forEach(function (raw) {
      var line = raw.trim(), m; if (!line) return;
      m = line.match(/^#+\s*(Article|Exhibit)\s+([A-Z0-9]+)/);
      if (m) { sec = parent = (m[1] === 'Exhibit' ? 'Exhibit ' : 'Art. ') + m[2]; return; }
      m = line.match(/^[-*]?\s*\**\s*(\d+(?:\.\d+){1,3})\b/); if (m) sec = parent = m[1];
      m = line.match(/^[-*]\s*\(([a-z])\)/); if (m && /^\d/.test(parent || '')) sec = parent + '(' + m[1] + ')';
      var clean = line.replace(/[*_`#]/g, '').trim().replace(/^[\s-]+|[\s-]+$/g, '');
      clean.split(/(?<=[.;])\s+(?=[A-Z(])/).forEach(function (part) {
        part = part.trim();
        if (part.length > 12 && !/^\(?[\d.a-z]+\)?\s+[A-Z][\w'&, -]{0,60}\.$/.test(part)) out.push({ id: 'S' + (out.length + 1), text: part, section: sec });
      });
    });
    return out;
  }
  function candidates(sents, keywords, k, numeric) {
    k = k || 6; if (numeric === undefined) numeric = true;
    var scored = [];
    sents.forEach(function (s, i) {
      var t = s.text.toLowerCase(), score = 0;
      keywords.forEach(function (w) { if (t.indexOf(w) >= 0) score += 2; });
      if (numeric && /\d/.test(t)) score += 1;
      if (score >= (numeric ? 3 : 2)) scored.push([score, i, s]);
    });
    scored.sort(function (a, b) { return b[0] - a[0] || a[1] - b[1]; });
    return scored.slice(0, k).map(function (x) { return x[2]; });
  }
  function isNumeric(kind) { return kind === 'pct' || kind === 'money' || kind === 'days'; }
  function retrieve(text) {
    var sents = sentences(text), c = {};
    TERMS.forEach(function (t) { c[t[0]] = candidates(sents, t[3], 6, isNumeric(t[2])); });
    return { sentences: sents, candidates: c };
  }
  function numbersIn(text) { return (String(text).match(/\d[\d,]*(?:\.\d+)?/g) || []).map(function (x) { return parseFloat(x.replace(/,/g, '')); }); }
  // Does the sentence actually say this value? Same rules as verify() in Python.
  function verify(kind, value, sentence) {
    if (!sentence) return [false, 'not stated'];
    var t = sentence.text.toLowerCase();
    if (isNumeric(kind)) { var v = parseFloat(value); if (!isFinite(v)) return [false, 'no value']; var ok = numbersIn(sentence.text).indexOf(v) >= 0; return [ok, ok ? 'value found in the sentence' : 'value not in the sentence']; }
    if (kind === 'fee_on') { var miss = (value || []).filter(function (p) { return !(FEE_WORDS[p] || [p.toLowerCase()]).some(function (w) { return t.indexOf(w) >= 0; }); }); var ok2 = !!(value && value.length) && !miss.length; return [ok2, ok2 ? 'categories found' : 'not all categories appear in the sentence']; }
    if (kind === 'parties') { var m2 = (value || []).filter(function (p) { return t.indexOf(p) < 0; }); var ok3 = !!(value && value.length) && !m2.length; return [ok3, ok3 ? 'parties found' : 'parties not in the sentence']; }
    if (kind === 'concurrent') return [t.indexOf('concurrent') >= 0, t.indexOf('concurrent') >= 0 ? 'mentions concurrent delay' : 'sentence doesn’t mention concurrent delay'];
    if (kind === 'bool') return [t.indexOf('critical path') >= 0, t.indexOf('critical path') >= 0 ? 'mentions the critical path' : 'sentence doesn’t mention the critical path'];
    return [false, 'unknown kind'];
  }
  // Per-term reading {key: {value, quote, section, status}} -> contract terms for ClauseChecks.fromTerms (spec section 3).
  function toTerms(read) {
    var t = {};
    Object.keys(read).forEach(function (k) { if (k.indexOf('notice_days_') !== 0) t[k] = { value: read[k].value, quote: read[k].quote, section: read[k].section, status: read[k].status }; });
    var std = read.notice_days_standard || {}, oth = read.notice_days_other || {};
    if (std.value != null || oth.value != null) {
      var by = {}; CAUSES.forEach(function (c) { by[c] = std.value; }); by['Other event'] = oth.value != null ? oth.value : std.value;
      t.notice_days_by_cause = { value: by, quote: std.quote, section: (std.section || '').split('(')[0], status: std.status === 'verified' && oth.status === 'verified' ? 'verified' : 'check' };
    }
    return t;
  }
  // The sample contract, as a reading, so it can be shown and edited the same way as a loaded one.
  function sampleReading(C) {
    function r(v, sec, q) { return { value: v, section: sec, quote: q || null, status: 'verified' }; }
    return {
      markup_own_pct: r(C.markupOwn, '6.5.2'), markup_lower_pct: r(C.markupLower, '6.5.2'), markup_total_pct: r(C.markupTotal, '6.5.2'),
      fee_pct: r(C.feePercent, '6.5.3'), fee_allowed_on: r(C.feeAllowedOn.slice(), '6.5.3'), labor_burden_pct: r(C.burdenPercent, '5.4'),
      blue_book_pct: r(C.blueBookPercent, '6.5.4'), approval_limit: r(C.approvalLimit, '6.7'),
      notice_days_standard: r(C.noticeByCause['RFI response'], '6.2(a)'), notice_days_other: r(C.noticeByCause['Other event'], '6.2(d)'),
      contract_days: r(C.contractDays, '3.2'), liquidated_damages_per_day: r(C.ldPerDay, '3.3'), daily_delay_rate: r(C.dailyDelayRate, '5.2'),
      sgc_total: r(C.sgcTotal, '5.2'), extension_requires_critical_path: r(C.extensionRequiresCriticalPath, '3.4'),
      compensable_causes: r(C.compensableCauses.slice(), '6.5.6'), concurrent_delay: r(C.concurrentDelay, '6.5.6')
    };
  }
  var api = { TERMS: TERMS, FEE_ON: FEE_ON, CONCURRENT: CONCURRENT, CAUSES: CAUSES, sentences: sentences, candidates: candidates, retrieve: retrieve, verify: verify, toTerms: toTerms, sampleReading: sampleReading, isNumeric: isNumeric };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.ClauseContract = api;
})(this);
