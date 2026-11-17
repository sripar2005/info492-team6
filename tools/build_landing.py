#!/usr/bin/env python3
"""Builds clausestream/index.html from the saved check sheets and tradeoff table, so the numbers
on the landing page are the ones in demo3/results. Run from the repo root: python tools/build_landing.py"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "demo3" / "results"
sheet = json.loads((R / "checksheets.json").read_text())["sheets"]["CP-0212"]
curve = json.loads((R / "tradeoff.json").read_text())["rows"]
ev = json.loads((R / "evaluation.json").read_text())["systems"]
e = html.escape
ST = {"pass": "pass", "fail": "fail", "person": "to a person", "not_checked": "not checked"}


def money(x):
    return f"${x:,.2f}"


rows = "".join(
    f'<tr class="{r["status"]}"><td><span class="st {r["status"]}">{ST[r["status"]]}</span></td><td>{e(r["check"])}</td>'
    f'<td data-l="Contract">{e(r["contract"])}</td><td data-l="Proposal">{e(r["proposal"])}</td>'
    f'<td class="num mono diff" data-l="Difference">{money(r["difference"]) if r["difference"] is not None else ""}</td>'
    f'<td class="mono" data-l="Clause" style="white-space:nowrap">{"§ " if r["section"][0].isdigit() else ""}{e(r["section"])}</td></tr>' for r in sheet["rows"])
n = sheet["counts"]
curve_rows = "".join(
    f'<tr><td>{e(r["configuration"].capitalize() if i == 0 else r["configuration"])}</td><td class="num mono">{r["caught"]}/{r["of"]}</td>'
    f'<td class="num mono">{r["clean_flagged"]}/{r["clean_total"]}</td><td class="num mono">{r["false_alarms"]}</td></tr>'
    for i, r in enumerate(curve))
m = {k: v["metrics"] for k, v in ev.items()}
ru, ll, ba = m["rules"], m["local-llama3.1-8b"], m["baseline"]
assert ru["issues_caught"] == 23 and ru["extra_flags"] == 0 and ru["clean_cases_flagged"] == 0

LOGO = '''<svg viewBox="0 0 28 28" aria-hidden="true"><rect x="0.5" y="0.5" width="27" height="27" rx="8" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.22)"/><path d="M6 22 L21 7" stroke="#eef2f6" stroke-width="1.6" stroke-linecap="round"/><path d="M15.5 7 H21 V12.5" stroke="#eef2f6" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="M8.6 17.4 l2 2 M11.8 14.2 l2 2 M15 11 l2 2" stroke="#ff6a3d" stroke-width="1.6" stroke-linecap="round"/><text x="5.2" y="12.2" font-family="Geist Mono, monospace" font-size="8.5" fill="#eef2f6">§</text></svg>'''

page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>ClauseStream</title>
<meta name="description" content="ClauseStream checks a priced change proposal against the contract before it is sent: markups, Fee, labor burden, equipment rates, notice dates and signatures, with the arithmetic shown.">
<meta name="theme-color" content="#07090c">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="/assets/cs.css">
<style>
.wrap {{ max-width: 1080px; margin: 0 auto; padding: 0 16px; }}
.topbar nav a.cta {{ color: #0a0d11; background: linear-gradient(180deg, #fff, #dfe5eb); font-weight: 500; }}
.hero {{ padding: 56px 0 22px; }}
.hero h1 {{ font-size: clamp(2rem, 5.4vw, 3.5rem); max-width: 17ch; margin-top: 14px; text-wrap: balance; }}
.lede {{ color: var(--muted); font-size: clamp(1rem, 1.6vw, 1.14rem); max-width: 62ch; margin: 18px 0 0; }}
.btns {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 24px; }}
section.s {{ padding: 44px 0 0; }}
section.s > .wrap > h2 {{ font-size: clamp(1.45rem, 3vw, 2.05rem); max-width: 24ch; margin-top: 10px; text-wrap: balance; }}
section.s > .wrap > p.sub {{ color: var(--muted); max-width: 68ch; margin: 12px 0 20px; }}
.card {{ padding: 22px; }}
.cap {{ display: flex; justify-content: space-between; gap: 10px 20px; flex-wrap: wrap; align-items: baseline; margin-bottom: 6px; }}
.cap h3 {{ font-size: clamp(1.15rem, 2.2vw, 1.45rem); }}
.cap .at {{ font: 500 .9rem/1 var(--mono); color: var(--warn); }}
.fine {{ color: var(--faint); font-size: .8rem; margin: 12px 0 0; max-width: 90ch; }}
.fine a, p a, li a {{ text-decoration: underline; text-decoration-color: var(--line-2); text-underline-offset: 3px; }}
.st {{ display: inline-block; min-width: 86px; padding: 3px 8px; border-radius: 7px; font: 500 .7rem/1.3 var(--mono); text-align: center; border: 1px solid var(--line-2); }}
.st.pass {{ color: var(--ok); border-color: rgba(79,209,165,.4); background: var(--ok-soft); }}
.st.fail {{ color: var(--warn); border-color: rgba(245,196,81,.45); background: var(--warn-soft); }}
.st.person {{ color: var(--accent); border-color: rgba(255,106,61,.45); background: var(--accent-soft); }}
.sheet td {{ font-size: .86rem; }}
.sheet tr.pass td {{ color: var(--muted); }} .sheet tr.pass td:nth-child(2) {{ color: var(--text); }}
.sheet .diff {{ color: var(--warn); font-weight: 500; }}
@media (max-width: 720px) {{
  .sheet thead {{ display: none; }}
  .sheet tr {{ display: grid; grid-template-columns: auto 1fr; gap: 4px 10px; padding: 10px 0; border-bottom: 1px solid var(--line); }}
  .sheet td {{ border: 0; padding: 0; }} .sheet td:nth-child(2) {{ font-weight: 500; }}
  .sheet td:nth-child(n+3) {{ grid-column: 1 / -1; }}
  .sheet td[data-l]::before {{ content: attr(data-l) ": "; color: var(--faint); font: 500 .7rem/1.4 var(--mono); }}
  .sheet td:empty {{ display: none; }}
}}
.two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
.three {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }}
@media (max-width: 820px) {{ .two, .three {{ grid-template-columns: 1fr; }} }}
.card h3 {{ font-size: 1.1rem; }}
.card p {{ color: var(--muted); margin: 8px 0 0; }}
.card .who {{ font: 500 .74rem/1.3 var(--mono); color: var(--faint); display: block; margin-bottom: 8px; }}
.big {{ font-size: clamp(1.9rem, 4vw, 2.6rem); font-weight: 600; letter-spacing: -0.04em; line-height: 1; display: block; }}
.big + span {{ color: var(--muted); font-size: .88rem; display: block; margin-top: 8px; }}
ul.plain {{ margin: 10px 0 0; padding-left: 18px; color: var(--muted); }} ul.plain li {{ margin: 6px 0; }}
figure.q {{ margin: 14px 0 0; padding: 22px; }}
figure.q p {{ font-size: clamp(1.05rem, 2vw, 1.3rem); margin: 0; letter-spacing: -0.01em; }}
figure.q footer {{ color: var(--faint); font: 500 .76rem/1.4 var(--mono); margin-top: 12px; }}
footer.site {{ margin-top: 56px; padding: 26px 0 40px; border-top: 1px solid var(--line); color: var(--faint); font-size: .82rem; }}
footer.site ol {{ padding-left: 18px; margin: 12px 0 0; }} footer.site li {{ margin: 5px 0; }}
footer.site .links {{ display: flex; gap: 14px; flex-wrap: wrap; margin-top: 8px; }}
sup a {{ color: var(--accent); font: 500 .68rem/1 var(--mono); }}
</style>
</head>
<body>
<div class="ambient" aria-hidden="true"></div>
<header class="topbar">
  <div class="bar glass">
    <a class="logo" href="/clausestream/" aria-label="ClauseStream home">{LOGO}<span>ClauseStream</span></a>
    <nav aria-label="ClauseStream">
      <a href="#sheet" class="hide-sm">The sheet</a>
      <a href="#measured" class="hide-sm">What we measured</a>
      <a href="/" class="hide-sm">Project site</a>
      <a class="cta" href="/app/">Open the dashboard</a>
    </nav>
  </div>
</header>

<main>
  <section class="hero">
    <div class="wrap">
      <span class="kicker">Pre-check for priced change proposals</span>
      <h1 class="shine">Check the change proposal against the contract before it is sent.</h1>
      <p class="lede">ClauseStream redoes the arithmetic an owner's reviewer would redo: markups, Fee, labor burden, equipment rates, notice dates, signatures. Each check shows what the contract says, what the proposal says, and the difference. Checks that pass are listed too, so you can see what was verified.</p>
      <div class="btns"><a class="btn primary" href="/app/">Open the dashboard →</a><a class="btn" href="/demo3/">Full results</a></div>
    </div>
  </section>

  <section class="s" id="sheet" style="padding-top:18px">
    <div class="wrap">
      <div class="card glass">
        <span class="kicker">{sheet["id"]} · {e(sheet["title"])} · {money(sheet["total_requested"])} requested</span>
        <div class="cap" style="margin-top:10px"><h3>{len(sheet["rows"])} checks: {n["pass"]} pass, {n["fail"]} fail, {n["person"]} goes to a person</h3><span class="at">{money(sheet["dollars_at_issue"])} at issue</span></div>
        <div class="tablewrap"><table class="sheet"><thead><tr><th>Result</th><th>Check</th><th>Contract says</th><th>Proposal says</th><th class="num">Difference</th><th>Clause</th></tr></thead><tbody>{rows}</tbody></table></div>
        <p class="fine">The 5% Fee was taken on $4,200 of dumpsters and haul-off that the contract excludes from the Fee: 5% of $4,200 is $210. Fee on excluded items is one of the findings in the Webster School audit.<sup><a href="#s1">1</a></sup> This is a synthetic test proposal on a synthetic contract, modeled on that audit. No AI model runs to produce this sheet.</p>
      </div>
    </div>
  </section>

  <section class="s" id="when">
    <div class="wrap">
      <span class="kicker">Same sheet, two moments</span>
      <h2 class="shine">Run it before you send. Read it when it arrives.</h2>
      <p class="sub">The checks are the owner's. Nothing stops the people preparing the proposal from running them first.</p>
      <div class="two">
        <div class="card glass"><span class="who">Before it is sent · Subcontractor, GC/CM</span><h3>Fix what would come back.</h3><p>A markup over the limit, an unsigned T&amp;M tag or a quote with no breakdown is knowable before submission. In a 2026 survey of specialty contractors, more than half of change order requests needed two or more revision cycles, and thin backup was one of the top two reasons payment was cut or held.<sup><a href="#s2">2</a></sup></p></div>
        <div class="card glass"><span class="who">On receipt · Architect, Owner's PM</span><h3>See what was verified. Spend your time on the rest.</h3><p>The sheet lists every check and its arithmetic, so a back-check takes seconds. It also says what it did not check: scope, reasonableness of hours and prices, and costs the Fee already covers. At Webster School, $129,531 in change-order charges was flagged 23 months after the last pay application.<sup><a href="#s1">1</a></sup></p></div>
      </div>
      <figure class="q glass"><p>“The markups, those are elements that are relatively easy to quantify. They're defined. If they're not defined in the contract, there's a problem.”</p><footer>Owner-side project manager, Lake Washington School District · 30+ years in construction</footer></figure>
    </div>
  </section>

  <section class="s" id="source">
    <div class="wrap">
      <span class="kicker">Where the checks come from</span>
      <h2 class="shine">The owner's checklist already exists. We compute the parts that are arithmetic.</h2>
      <p class="sub">The Washington State Auditor publishes guidance for reviewing change orders.<sup><a href="#s3">3</a></sup> One item reads, in full: “Recalculate overhead and markup calculations.” This is how its items line up with the sheet.</p>
      <div class="card glass"><div class="tablewrap"><table>
        <thead><tr><th>State Auditor guidance asks the owner to</th><th>On the sheet</th></tr></thead><tbody>
        <tr><td>Recalculate overhead and markup</td><td>Sub markup, Fee rate, Fee base, cover sheet tie-out</td></tr>
        <tr><td>Get an itemized breakdown of labor, material, equipment and markup</td><td>Itemized breakdown, signed T&amp;M tags, lines add up</td></tr>
        <tr><td>Verify labor rates against a set basis</td><td>Labor burden at the contract rate</td></tr>
        <tr><td>Price equipment against the Rental Rate Blue Book</td><td>Owned equipment rate</td></tr>
        <tr><td>Define who may approve and the dollar limits</td><td>Approval limit, sent to a person</td></tr>
        <tr><td>Confirm the owner has not already paid for the same thing</td><td class="muted">Not computed. It turns on what a line item means, so it stays with a person.</td></tr>
        <tr><td>Judge hours and quantities for reasonableness</td><td class="muted">Not computed.</td></tr>
        </tbody></table></div></div>
      <p class="sub" style="margin-top:20px">Public audits elsewhere report the same kinds of findings:</p>
      <div class="three">
        <div class="card glass"><span class="big">$139,137</span><span>Change-order labor costs questioned: billed at rates that included overhead and profit, where the contract allowed direct wages plus a defined burden. The contractor disputed the finding. Louisiana Legislative Auditor, Recovery School District.<sup><a href="#s4">4</a></sup></span></div>
        <div class="card glass"><span class="big">55</span><span>Change orders on one Los Angeles Unified contract with overbilled bond costs, $1,669 in total. LAUSD Office of the Inspector General.<sup><a href="#s5">5</a></sup></span></div>
        <div class="card glass"><span class="big">$8.7M</span><span>Ineligible costs from change orders over the allowed maximum in Connecticut's school construction grants, fiscal years 2021 and 2022.<sup><a href="#s6">6</a></sup></span></div>
      </div>
    </div>
  </section>

  <section class="s" id="measured">
    <div class="wrap">
      <span class="kicker">What we measured</span>
      <h2 class="shine">The computed checks raised no false alarms. They also cannot see everything.</h2>
      <p class="sub">We scored the sheet on our 36 synthetic change proposals, which carry 33 planted issues and 10 clean proposals, against the same answer key as Demo 3.</p>
      <div class="three">
        <div class="card glass"><span class="big">{ru["issues_caught"]}/{ru["seeded_issues"]}</span><span>planted issues caught by the computed checks</span></div>
        <div class="card glass"><span class="big">{ru["extra_flags"]}</span><span>false alarms, and {ru["clean_cases_flagged"]} of {ru["clean_cases"]} clean proposals flagged</span></div>
        <div class="card glass"><span class="big">6/6</span><span>delay claims, site conditions and over-limit amounts sent to a person</span></div>
      </div>
      <div class="two" style="margin-top:14px">
        <div class="card glass"><h3>The 10 it cannot reach</h3><ul class="plain"><li>4 costs the Fee already covers</li><li>2 equipment items that belong in general conditions or site services, not the proposal</li><li>1 item that was not really a change</li><li>3 problems inside subcontractor quotes that arrived as email text</li></ul><p>Seven need judgment about meaning. Three need someone to read an email. The sheet marks those quotes “not checked” and does not guess.</p></div>
        <div class="card glass"><h3>What the agents add, and cost</h3><p>Demo 3's four role agents ran on a free 8B model. On their own they caught {ll["issues_caught"]}/{ll["seeded_issues"]} with {ll["extra_flags"]} false alarms. Layered on the sheet, they find most of the missing 10, and flag every clean proposal while doing it.</p>
          <div class="tablewrap" style="margin-top:10px"><table><thead><tr><th>Setup</th><th class="num">Caught</th><th class="num">Clean flagged</th><th class="num">False alarms</th></tr></thead><tbody>{curve_rows}</tbody></table></div></div>
      </div>
      <p class="fine">For comparison, Demo 3's rules-and-keywords checker caught {ba["issues_caught"]}/{ba["seeded_issues"]} with {ba["extra_flags"]} false alarms and {ba["clean_cases_flagged"]} of {ba["clean_cases"]} clean proposals flagged. It scores higher than the sheet because its keyword lists guess at meaning. With this model there is no setting that adds catches without adding noise, so in the dashboard the agent reviews are collapsed and labeled as unverified leads. <a href="/demo3/">Full results and per-proposal traces</a>.</p>
    </div>
  </section>

  <section class="s" id="limits">
    <div class="wrap">
      <span class="kicker">Limits</span>
      <h2 class="shine">What this does not show yet.</h2>
      <div class="card glass" style="margin-top:18px"><ul class="plain" style="margin-top:0">
        <li><b style="color:var(--text);font-weight:500">The test proposals are structured data.</b> Real ones arrive as PDFs and spreadsheets and have to be read into fields first. We have not built or tested that step.</li>
        <li>Our team wrote the contract, the proposals, the planted issues and the checks, with AI assistance, so the test favors what we expected. Which checks moved into code was decided after the Demo 3 runs; the cases, answer key and agent prompts were not changed.</li>
        <li>One synthetic GC/CM contract. Thresholds are that contract's; another contract needs its own.</li>
        <li>No subcontractor or GC/CM has used it. The “before it is sent” case rests on a published survey, not on our own testing.</li>
      </ul></div>
      <div class="btns"><a class="btn primary" href="/app/">Open the dashboard →</a><a class="btn" href="/demos/">All demos</a><a class="btn" href="/thesis/">Thesis</a></div>
    </div>
  </section>
</main>

<footer class="site">
  <div class="wrap">
    <span>ClauseStream · Team 6: Yousuf Shaik, Sriharshith Paruchuri, Nithika Yechuri · INFO 492 C, University of Washington Information School · 2026</span>
    <div class="links"><a href="/">Overview</a><a href="/thesis/">Thesis</a><a href="/demos/">Demos</a><a href="/demo3/">Demo 3 results</a><a href="/log/">Log</a><a href="/sources/">Sources</a><a href="https://github.com/sripar2005/info492-team6">Code</a></div>
    <ol>
      <li id="s1"><a href="https://www.seattleschools.org/wp-content/uploads/2024/03/Webster-School-Modernization-and-Addition-Audit-ADA.pdf">Webster School Modernization and Addition audit, Seattle Public Schools, December 2023</a></li>
      <li id="s2"><a href="https://www.clearstory.build/construction-blog/2026-sc-change-order-report">Clearstory and Dodge Construction Network, change order research on specialty trade contractors, 2026 (vendor summary)</a></li>
      <li id="s3"><a href="https://sao.wa.gov/sites/default/files/2023-05/Change-Order-Best-practices.pdf">Office of the Washington State Auditor, “Best practices for change orders”</a></li>
      <li id="s4"><a href="https://www.lla.state.la.us/PublicReports.nsf/D37141BC3E866E5586257B42006D57FE/$FILE/00031562.pdf">Louisiana Legislative Auditor, compliance audit of the Recovery School District's modular campus construction</a></li>
      <li id="s5"><a href="https://media.edlio.net/594f6250/1b9a3fa8/32f1693a/5ea89ad987c44f0eb2760be3ddc1501f?_=CA+26-1013+Incurred+Cost+Audit+Pinmor+Contstruction+Cont+No+4400009538.pdf">Los Angeles Unified School District, Office of the Inspector General, incurred cost audit CA 26-1013</a></li>
      <li id="s6"><a href="https://insideinvestigator.org/auditors-276-million-of-overspending-discrepancies-in-school-construction-grants/">Inside Investigator, report on the Connecticut state auditors' review of school construction grants</a></li>
    </ol>
  </div>
</footer>
</body>
</html>
'''
(ROOT / "clausestream" / "index.html").write_text(page)
print("wrote clausestream/index.html", len(page))
