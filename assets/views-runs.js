/* Agent runs: the RFI responder on real public RFIs, scored by code against the official published answers.
   Reads the committed results (data/real/results/), so every number here can be reproduced from the repo. */
(function () {
  'use strict';
  var A = window.CSApp, esc = A.esc, app = A.app;
  var V = window.CSViews = window.CSViews || {};
  var J = {}, sel = { project: null, model: null };
  function get(u) { if (!J[u]) J[u] = fetch(u).then(function (r) { if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); }); return J[u]; }
  function norm(s) { return ((s || '').toLowerCase().match(/[a-z0-9]+/g) || []).join(' '); }
  function pct(x) { return x == null ? '—' : Math.round(x * 100) + '%'; }
  function slug(m) { return m.replace(/[^A-Za-z0-9._-]/g, '_'); }

  var MEASURES = [
    ['citations_verified', 'Citations found word for word in the documents', 'Every quote is checked against the excerpt it names. Fabricated excerpt ids count as failures.', function (s) { return pct(s.citations_verified) + (s.citations_fabricated_ids ? ' <span class="bad">(' + s.citations_fabricated_ids + ' made-up ids)</span>' : ''); }, function () { return '—'; }],
    ['answers_fully_supported', 'Answers where every citation checks out', 'Of the answers that cite anything.', function (s) { return pct(s.answers_fully_supported); }, function () { return '—'; }],
    ['decision_agreement', 'Yes/no answers that match the official answer', 'RFIs whose official answer is a plain yes or no.', function (s) { return pct(s.decision_agreement) + ' <span class="fine">of ' + s.decision_n + '</span>'; }, function (b) { var k = Object.keys(b)[0]; return k ? pct(b[k]) + ' <span class="fine">always “' + k.split('_').pop() + '”</span>' : '—'; }],
    ['new_information_flagged', 'Handed to a person when the answer needed new information', 'The official answer supplied something not in the documents (an addendum, an attachment, “will be provided”). Read with the next row.', function (s) { return pct(s.new_information_flagged) + ' <span class="fine">of ' + s.new_information_n + '</span>'; }, function () { return '—'; }],
    ['asked_for_a_person', 'Asked for a person, all RFIs', 'How often the agent said the documents don’t settle it.', function (s) { return pct(s.asked_for_a_person); }, function () { return '—'; }],
    ['answer_overlap_f1', 'Wording overlap with the official answer (F1)', 'Word-overlap score from 0 to 1, as used to score question answering. Baseline: the top search result’s opening words.', function (s) { return s.answer_overlap_f1 == null ? '—' : s.answer_overlap_f1.toFixed(2); }, function (b, s) { return s && s.answer_overlap_f1_baseline_top_search_text != null ? s.answer_overlap_f1_baseline_top_search_text.toFixed(2) : '—'; }],
    ['reference_resolution', 'Spec sections named in the RFI that the agent found and cited', 'Few bid-phase RFIs name a spec section that is in the public documents (most point to drawings), so this sample is small.', function (s) { return pct(s.reference_resolution) + ' <span class="fine">of ' + s.reference_n + '</span>'; }, function (b, s) { return s ? pct(s.reference_resolution_top_search_result) + ' <span class="fine">keyword search</span>' : '—'; }],
    ['median_seconds_per_rfi', 'Median seconds per RFI', 'On GitHub’s free machines (4 CPU cores, no GPU). A laptop with Apple silicon is several times faster.', function (s) { return s.median_seconds_per_rfi == null ? '—' : Math.round(s.median_seconds_per_rfi) + ' s'; }, function () { return '—'; }]
  ];

  V.runs = function () {
    app.innerHTML = '<div class="wrap"><div class="ph1"><div><span class="eyebrow">07 Agent runs</span><h1 style="margin-top:8px">Agent runs on real RFIs</h1></div></div><p class="fine">Loading the results…</p></div>';
    Promise.all([get('/data/real/rfis.json'), get('/data/real/results/summary.json').catch(function () { return null; })]).then(function (r) { draw(r[0], r[1]); })
      .catch(function (e) { app.querySelector('.fine').textContent = 'Could not load the results: ' + e.message; });
  };

  function draw(R, S) {
    var models = S ? Object.keys(S.models) : [];
    if (!sel.project) sel.project = R.projects[0].project;
    if (!sel.model) sel.model = models[models.length - 1] || null;
    var srcs = R.projects.map(function (p) { return '<li><b>' + esc(p.name) + '</b> · ' + p.rfis + ' RFIs</li>'; }).join('');
    var head = '<p class="lede gs-lede">An agent answers contractors’ RFIs the way the owner or design team would: it searches the project’s own contract and spec documents, drafts a response, and quotes the excerpts it relied on. Code then checks it against the answers the agencies actually published.</p>' +
      '<div class="cols" style="--cols: minmax(0,1.2fr) minmax(0,1fr)"><div class="card sec"><div class="sec-h"><h3>The data: real public records</h3><span class="tagr ok">real</span></div>' +
      '<p style="margin:0 0 8px">' + (S ? S.rfis_available : R.rfis.length) + ' RFIs with their official published answers, from ' + R.projects.length + ' public projects. Public agencies must disclose these records; our owner’s-rep stakeholder pointed us to them.</p><ul class="plain" style="margin:0">' + srcs + '</ul>' +
      '<p class="fine" style="margin:10px 0 0">The source PDFs, their download dates and checksums, and the extracted RFIs are in the repository (<a class="link" href="https://github.com/sripar2005/info492-team6/tree/main/data/real" target="_blank" rel="noopener">data/real</a>). Nothing is edited by hand.</p></div>' +
      '<div class="card sec"><div class="sec-h"><h3>Reproduce it</h3></div><pre class="checkout" style="white-space:pre-wrap;margin:0">python3 tools/real/fetch.py      # download the public records\npython3 tools/real/extract.py    # RFIs, answers, document pieces\npython3 tools/real/rfi_eval.py --model qwen3.5:9b\npython3 tools/real/score.py      # the numbers on this page</pre>' +
      '<p class="fine" style="margin:10px 0 0">Or on GitHub’s free machines: Actions → “Real RFI evaluation” → Run workflow. Free local models through Ollama; no API key, nothing sent to a cloud AI.</p></div></div>';
    var board;
    if (!S) board = '<div class="card sec" style="margin-top:16px"><p style="margin:0">The models are still running. Results appear here when the evaluation finishes.</p></div>';
    else {
      var best = {};
      ['citations_verified', 'answers_fully_supported', 'decision_agreement', 'new_information_flagged', 'answer_overlap_f1', 'reference_resolution'].forEach(function (k) {
        var v = models.map(function (m) { return S.models[m][k]; }), mx = Math.max.apply(null, v.filter(function (x) { return x != null; }));
        best[k] = models.filter(function (m) { return S.models[m][k] === mx; });
      });
      var ref = S.models[models[0]];
      board = '<div class="card tbl-wrap" style="margin-top:16px"><table class="tbl runs"><thead><tr><th>Measure</th>' + models.map(function (m) { return '<th>' + esc(m) + '<div class="fine">' + S.models[m].rfis_run + ' RFIs</div></th>'; }).join('') + '<th>No AI<div class="fine">baseline</div></th></tr></thead><tbody>' +
        MEASURES.map(function (M) {
          return '<tr><td><b>' + esc(M[1]) + '</b><div class="fine">' + esc(M[2]) + '</div></td>' + models.map(function (m) { return '<td class="' + ((best[M[0]] || []).indexOf(m) >= 0 && models.length > 1 ? 'best' : '') + '">' + M[3](S.models[m]) + '</td>'; }).join('') + '<td>' + M[4](S.baselines, ref) + '</td></tr>';
        }).join('') + '</tbody></table></div>' +
        '<p class="fine" style="margin:8px 0 0">Best result in each row in bold. Same search step for every model (keyword search plus the ' + esc((ref.embed_model || [''])[0] || 'embedding') + ' embedding model), 6 excerpts per RFI, temperature 0. How each measure is computed: <a class="link" href="https://github.com/sripar2005/info492-team6/blob/main/tools/real/score.py" target="_blank" rel="noopener">tools/real/score.py</a>.</p>';
    }
    var picker = '<div class="grid filt" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr);margin-top:26px"><div class="fd"><label><span>Project</span></label><div class="inp sel"><select id="rproj">' +
      R.projects.map(function (p) { return '<option value="' + p.project + '"' + (p.project === sel.project ? ' selected' : '') + '>' + esc(p.name) + '</option>'; }).join('') + '</select></div></div>' +
      '<div class="fd"><label><span>Model</span></label><div class="inp sel"><select id="rmodel">' + models.map(function (m) { return '<option' + (m === sel.model ? ' selected' : '') + '>' + esc(m) + '</option>'; }).join('') + '</select></div></div></div><div id="rlist"><p class="fine">Loading…</p></div>';
    app.innerHTML = '<div class="wrap"><div class="ph1"><div><span class="eyebrow">07 Agent runs</span><h1 style="margin-top:8px">Agent runs on real RFIs</h1></div></div>' + head + board +
      '<h2 class="gs-h">Each RFI, side by side</h2><p class="fine gs-sub">The contractor’s question, the official answer, and the agent’s draft. Green citations were found word for word; red ones were not.</p>' + (models.length ? picker : '<p class="fine">Available once the models finish.</p>') +
      '<h2 class="gs-h">Tested on synthetic data</h2><p class="fine gs-sub">Earlier demos and the platform’s computed checks run on a synthetic school project written for this research with AI assistance, scored against answer keys a separate helper wrote: <a class="link" href="/demo3/">Demo 3 evaluation</a>, platform checks (107 of 107 against the helper’s answer key), delay analysis (20 change orders). These are clearly not real-world figures.</p></div>';
    var rp = document.getElementById('rproj'), rm = document.getElementById('rmodel');
    if (rp) { rp.onchange = function () { sel.project = rp.value; list(R); }; rm.onchange = function () { sel.model = rm.value; list(R); }; list(R); }
  }

  function list(R) {
    var el = document.getElementById('rlist'); el.innerHTML = '<p class="fine">Loading…</p>';
    Promise.all([get('/data/real/results/' + slug(sel.model) + '/' + sel.project + '.json'), get('/data/real/docs/' + sel.project + '.json')]).then(function (r) {
      var run = r[0], pieces = {}; r[1].pieces.forEach(function (p) { pieces[p.id] = p; });
      el.innerHTML = run.rows.map(function (row) {
        var o = row.output || {}, cits = Array.isArray(o.citations) ? o.citations : [];
        var c = cits.map(function (x) {
          var p = pieces[x.piece], ok = p && row.retrieved.indexOf(x.piece) >= 0 && norm(x.quote).split(' ').length >= 4 && norm(p.text).indexOf(norm(x.quote)) >= 0;
          return '<li class="' + (ok ? 'ok' : 'miss') + '">' + (ok ? '✓ ' : '✗ ') + (p ? esc(p.doc) + ', ' + esc(p.section) + (p.title ? ' ' + esc(p.title) : '') : 'excerpt ' + esc(x.piece) + ' (not one it was given)') + '<div class="fine">“' + esc(x.quote || '') + '”</div></li>';
        }).join('');
        return '<div class="card sec runrow"><div class="fine">' + esc(row.id.split(':').slice(1).join(' · ')) + (row.discipline ? ' · answered by ' + esc(row.discipline) : '') + '</div>' +
          '<p style="margin:6px 0 10px"><b>RFI:</b> ' + esc(row.question) + '</p>' +
          '<div class="cols" style="--cols: minmax(0,1fr) minmax(0,1fr)"><div><div class="fine">Official answer, as published</div><p style="margin:4px 0 0">' + esc(row.official_answer) + '</p></div>' +
          '<div><div class="fine ai-l">AI draft · ' + esc(run.model) + (o.decision ? ' · ' + esc(o.decision) : '') + (o.needs_person ? ' · <span class="turnword">asks for a person</span>' : '') + '</div><pre class="draft ai" style="margin:4px 0 0;white-space:pre-wrap">' + esc(o.answer || o.error || '(no answer)') + '</pre>' +
          (c ? '<ul class="cites plain" style="margin:8px 0 0">' + c + '</ul>' : '<p class="fine" style="margin:6px 0 0">No citations.</p>') + '</div></div></div>';
      }).join('');
    }).catch(function () { el.innerHTML = '<p class="fine">No results for this model on this project yet.</p>'; });
  }
})();
