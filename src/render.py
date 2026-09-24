"""Render index.html - see module docstring in render_charts.py for design notes."""
from __future__ import annotations

import datetime as dt
import json

from render_charts import (C, GATE_COLORS, GATE_SHORT, AUTH_COLORS,
                           VERDICT_COLORS, esc, svg_accuracy_bars,
                           svg_donut, svg_hstack_bars, svg_pipeline,
                           svg_ranked_bars)
from render_css import CSS
from config import (AUDIT_JSON, COMPOSIO_JSON, DRAFT_CSV, DRAFT_META,
                    INDEX_HTML, OVERRIDES_CSV, PASS2_CSV, PATTERNS_JSON,
                    RESEARCH_DRAFTS, VERIFY_JSON)
from io_utils import read_csv, read_json

NAV = [("patterns", "Patterns"), ("matrix", "The 100 apps"),
       ("agent", "The agent"), ("verification", "Verification"),
       ("run", "Run it"), ("honesty", "Honesty")]


def pct(v: float) -> str:
    return f"{v * 100:.0f}%"


def build_rows(pass2, patterns) -> list[dict]:
    tier_map = {}
    for t, ids in patterns["tiers"]["ids"].items():
        for i in ids:
            tier_map[i] = t
    ver2 = read_json(VERIFY_JSON[2])
    ev_status = {p["id"]: p["evidence"] for p in ver2["per_row"]}
    rows = []
    for r in pass2:
        rid = int(r["id"])
        rows.append({
            "id": rid, "name": r["name"], "category": r["category"],
            "website": r["website"], "does": r["does"], "auth": r["auth"],
            "auth_detail": r["auth_detail"], "gate": r["gate"],
            "gate_detail": r["gate_detail"], "surface": r["surface"],
            "breadth": r["breadth"], "mcp": r["mcp"],
            "mcp_evidence": r.get("mcp_evidence", ""),
            "verdict": r["verdict"], "blocker": r["blocker"],
            "evidence": r["evidence"], "confidence": int(r["confidence"] or 3),
            "notes": r.get("notes", ""), "tier": tier_map.get(rid, "C"),
            "ev_status": [c.get("status", 0) for c in ev_status.get(rid, [])],
        })
    return rows


def render() -> None:  # noqa: C901 - one big template, sections labeled
    patterns = read_json(PATTERNS_JSON)
    ver1 = read_json(VERIFY_JSON[1])
    ver2 = read_json(VERIFY_JSON[2])
    aud1 = read_json(AUDIT_JSON[1])
    aud2 = read_json(AUDIT_JSON[2])
    pass2 = read_csv(PASS2_CSV)
    draft_meta = read_json(DRAFT_META) if DRAFT_META.exists() else {}
    overrides = read_csv(OVERRIDES_CSV)
    proposals = read_csv(RESEARCH_DRAFTS)
    try:
        composio = read_json(COMPOSIO_JSON)
    except FileNotFoundError:
        composio = {}
    rows = build_rows(pass2, patterns)
    today = dt.date.today().isoformat()

    # ------------------------------------------------------------ derived
    self_serve = sum(1 for r in pass2
                     if r["gate"] in ("Open self-serve", "Paid self-serve"))
    sales = sum(1 for r in pass2 if r["gate"] == "Contact sales / partner")
    admin_g = sum(1 for r in pass2 if r["gate"] == "Admin approval")
    no_api = sum(1 for r in pass2 if r["surface"] == "No public API")
    official_mcp = sum(1 for r in pass2 if r["mcp"] == "Yes (official)")
    ready = sum(1 for r in pass2 if r["verdict"] == "Ready")
    ready_c = sum(1 for r in pass2 if r["verdict"] == "Ready with caveats")
    blocked = sum(1 for r in pass2 if r["verdict"] == "Blocked")
    easy_wins = patterns["easy_wins"]
    delta = (aud2["field_accuracy"] - aud1["field_accuracy"]) * 100

    # ------------------------------------------------------------ hero
    tiles = f"""
<div class="tiles">
  <div class="tile"><div class="big">100<span class="to"> × </span>10</div>
    <div class="lab">apps researched · categories</div></div>
  <div class="tile hero-acc"><div class="big">{pct(aud1['field_accuracy'])}
    <span class="to">→</span> {pct(aud2['field_accuracy'])}</div>
    <div class="lab">audit accuracy, pass 1 → pass 2 (+{delta:.0f} pts)</div></div>
  <div class="tile"><div class="big">{ver2['rows_with_live_evidence']}/{ver2['rows']}</div>
    <div class="lab">rows with live evidence (HTTP 200)</div></div>
  <div class="tile"><div class="big">{self_serve}<span class="to">/</span>100</div>
    <div class="lab">self-serve for a developer today</div></div>
  <div class="tile"><div class="big">{official_mcp}</div>
    <div class="lab">official MCP servers found</div></div>
  <div class="tile"><div class="big">{len(easy_wins)}</div>
    <div class="lab">easy wins - build-shortlist</div></div>
</div>"""

    hero = f"""
<header class="hero" id="top"><div class="wrap">
  <div class="kicker">AI Product Ops · Take-home case study · Composio</div>
  <h1>100 apps. One research agent.<br>Every claim <span class="accent">sourced</span>,
    every error <span class="accent">shown</span>.</h1>
  <p class="sub">An agent drafted the auth, gating, API surface and MCP status of
    <b>100 apps across 10 categories</b> from its own knowledge - then a live
    verification loop (HTTP evidence checks + contradiction rules + a deep-dive
    agent) and a human review pass pushed audit accuracy from
    <b>{pct(aud1['field_accuracy'])} to {pct(aud2['field_accuracy'])}</b>.
    This page is the deliverable: findings, patterns, the pipeline that produced
    them, and the receipts.</p>
  {tiles}
  <div class="verdict-strip"><span class="k">THE ANSWER</span>
    <span>Build now: <b>{self_serve} self-serve apps</b> (documented APIs, credentials
    in minutes). <b>{len(easy_wins)} easy wins</b> still lack an official MCP server.
    <b>{sales} apps</b> need outreach first; <b>{admin_g}</b> need workspace-admin
    approval; <b>{no_api}</b> have no public API at all - a hard stop.</span></div>
  <div class="asof">Research window: September 2026 · draft model
    {esc(draft_meta.get('model', 'gemini'))} (memory-only) · verified
    {today} · full data in <a href="out/research_report.json">out/research_report.json</a>
  </div>
</div></header>"""

    # ------------------------------------------------------------ patterns
    pat_cards = "".join(
        f'<div class="card"><span class="rank">pattern {p["rank"]:02d}</span>'
        f'<div class="metric">{esc(p["metric"])}'
        f'<span class="mlab">{esc(p["metric_label"])}</span></div>'
        f'<h3>{esc(p["claim"])}</h3><p>{esc(p["detail"])}</p></div>'
        for p in patterns["headline"])

    gate_rows = sorted(
        ({"label": cat, "n": v["n"], "pct": f'{v["self_serve_pct"]}%',
          "parts": v["gates"]} for cat, v in patterns["gate_by_category"].items()),
        key=lambda r: -(r["parts"].get("Open self-serve", 0)
                        + r["parts"].get("Paid self-serve", 0)) / max(r["n"], 1))
    gate_chart = svg_hstack_bars(gate_rows, GATE_COLORS, GATE_SHORT)
    gate_legend = '<div class="legend-list">' + "".join(
        f'<span><span class="sw" style="background:{GATE_COLORS[k]}"></span>'
        f'{esc(GATE_SHORT[k])}</span>'
        for k in ("Open self-serve", "Paid self-serve", "Admin approval",
                  "Contact sales / partner", "N/A (no auth)")) + "</div>"

    auth_donut = svg_donut(patterns["auth_dist"], AUTH_COLORS)
    auth_legend = '<div class="legend-list">' + "".join(
        f'<span><span class="sw" style="background:{AUTH_COLORS[k]}"></span>'
        f'{esc(k)} · {v}</span>'
        for k, v in patterns["auth_dist"].items()) + "</div>"

    mcp_rows = [{"label": cat, "n": v["n"], "pct": f'{v["any"]}',
                 "parts": {"Yes (official)": v["official"],
                           "Yes (community)": v["community"]}}
                for cat, v in patterns["mcp_by_category"].items()]
    mcp_chart = svg_hstack_bars(mcp_rows, {"Yes (official)": C["official"],
                                           "Yes (community)": C["community"]},
                                {"Yes (official)": "official MCP",
                                 "Yes (community)": "community MCP"})
    mcp_legend = ('<div class="legend-list">'
                  f'<span><span class="sw" style="background:{C["official"]}"></span>'
                  f'official · {official_mcp}</span>'
                  f'<span><span class="sw" style="background:{C["community"]}"></span>'
                  f'community · {sum(1 for r in pass2 if r["mcp"] == "Yes (community)")}'
                  f'</span><span>none · '
                  f'{sum(1 for r in pass2 if r["mcp"] == "No")}</span></div>')

    blocker_chart = svg_ranked_bars(patterns["blocker_clusters"], C["sales"])
    wins_html = "".join(
        f'<li><span class="nm"><a href="#matrix" onclick="jumpTo({w["id"]})">'
        f'{esc(w["name"])}</a></span><span class="ct">{esc(w["category"])} · '
        f'{esc(w["gate"])}</span></li>'
        for w in easy_wins[:40]) or '<li>none found</li>'
    outreach_html = "".join(
        f'<li><span class="nm">{esc(o["name"])}</span>'
        f'<span class="ct">{esc(o["blocker"] or o["category"])}</span></li>'
        for o in patterns["needs_outreach"][:40]) or '<li>none</li>'

    patterns_sec = f"""
<section id="patterns"><div class="wrap">
  <div class="shead"><div class="snum">01 — THE HEADLINE</div>
    <h2>Seven patterns that decide where toolkits get built</h2>
    <p class="slede">Computed from the verified dataset - not hand-written.
      Each claim below carries its number; the charts show the shape behind it.</p>
  </div>
  <div class="cards">{pat_cards}</div>
  <div class="charts">
    <div class="chart"><h4>Auth methods across the 100</h4>
      <div class="csub">primary API auth, verified dataset</div>
      <div class="donut-wrap">{auth_donut}{auth_legend}</div></div>
    <div class="chart"><h4>Who lets a developer self-serve?</h4>
      <div class="csub">gating mix per category, sorted by self-serve share</div>
      {gate_chart}{gate_legend}</div>
    <div class="chart"><h4>MCP coverage by category</h4>
      <div class="csub">official vs community MCP servers, per category</div>
      {mcp_chart}{mcp_legend}</div>
    <div class="chart"><h4>Why the blocked apps are blocked</h4>
      <div class="csub">clustered main blocker, {blocked} blocked apps</div>
      {blocker_chart}</div>
  </div>
  <div class="two-col">
    <div class="chart"><h4><span class="pill g">easy wins</span>&nbsp;
      {len(easy_wins)} apps you can build against today - no official MCP yet</h4>
      <div class="csub">self-serve credentials + documented REST/GraphQL + MCP "No"
        · click to open in the matrix</div>
      <ul class="winlist">{wins_html}</ul></div>
    <div class="chart"><h4><span class="pill r">needs outreach</span>&nbsp;
      {sales} apps gated behind sales or partnerships</h4>
      <div class="csub">no engineering unblocks these - partnerships do</div>
      <ul class="outlist">{outreach_html}</ul></div>
  </div>
</div></section>"""

    # ------------------------------------------------------------ matrix
    data_js = json.dumps({"rows": rows}, ensure_ascii=False)
    matrix_sec = f"""
<section id="matrix"><div class="wrap">
  <div class="shead"><div class="snum">02 — THE MATRIX</div>
    <h2>All 100 apps, skimmable in two minutes</h2>
    <p class="slede">Sort, filter, search. Click any row for details and evidence.
      Verdict: <b style="color:{C['ready']}">Ready</b> ·
      <b style="color:{C['caveat']}">Ready with caveats</b> ·
      <b style="color:{C['blocked']}">Blocked</b>. Tier S/A/B/C = composite
      toolkit-readiness (gating + API surface + MCP gap). Every app links to the
      doc its row was verified against.</p>
  </div>
  <div class="controls">
    <input type="search" id="q" placeholder="Search app, auth, blocker…">
    <div class="chipset" id="cats"><span class="chip on" data-v="">All</span></div>
    <select id="fVerdict"><option value="">Any verdict</option>
      <option>Ready</option><option>Ready with caveats</option>
      <option>Blocked</option></select>
    <select id="fMcp"><option value="">Any MCP</option>
      <option>Yes (official)</option><option>Yes (community)</option>
      <option>No</option><option>Unclear</option></select>
    <select id="fTier"><option value="">Any tier</option>
      <option>S</option><option>A</option><option>B</option><option>C</option></select>
    <button class="btn" id="csvBtn">Export CSV</button>
    <span class="count" id="count"></span>
  </div>
  <div class="table-scroll"><table id="tbl"><thead><tr>
    <th data-k="id">#</th><th data-k="name">App</th><th data-k="does">What it does</th>
    <th data-k="auth">Auth</th><th data-k="gate">Gating</th>
    <th data-k="surface">API surface</th><th data-k="mcp">MCP</th>
    <th data-k="tier">Tier</th><th data-k="verdict">Verdict</th>
    <th data-k="evidence">Evidence</th><th data-k="confidence">Conf</th>
  </tr></thead><tbody id="tbody"></tbody></table></div>
</div></section>
<script id="report-data" type="application/json">{data_js}</script>"""

    # ------------------------------------------------------------ agent
    n_flag = ver1["flagged_rows"]
    n_prop = len(proposals)
    n_over = len(overrides)
    pipe_svg = svg_pipeline(n_flag, n_prop, n_over)
    calls = draft_meta.get("calls", "?")
    stages = [
        ("1", "Pass 1 — the draft agent", "LLM drafts all 100 apps from its own "
         "knowledge, batched 10/call, no web access. This is the honest starting "
         "point: fast, broad, and wrong in instructive ways.",
         f"{calls} Gemini calls · cached to out/llm_cache/"),
        ("2", "Verify — live evidence loop", "Every evidence URL is fetched: HTTP "
         "status, redirects, and page-text sniffing for auth/API keywords. A rule "
         "engine adds cross-field contradiction checks.",
         f"{ver1['evidence_urls']} URLs pass 1 · requests + ThreadPool"),
        ("3", "Deep-dive — the research agent", "Flagged rows get their real docs "
         "pages fetched; an LLM extracts facts strictly from that text with "
         "verbatim quotes. Output: proposals, never auto-applied.",
         f"{n_flag} rows flagged → {n_prop} proposals"),
        ("4", "Human review — the loop's exit", "Proposals are reviewed by a human "
         "who promotes corrections into data/overrides.csv. The dataset ships "
         "with the promoted ledger; every change is traceable.",
         f"{n_over} field corrections promoted"),
        ("5", "Pass 2 + independent audit", "Overrides are applied, the whole pass "
         "is re-verified, and both passes are scored against a hand-built ground "
         "truth sample fixed before grading.",
         "audit: 20 apps × 5 fields, strict match"),
        ("6", "Patterns + page", "Distributions, clusters and the headline "
         "insights are computed from the final dataset; this page is generated "
         "from the artifacts.",
         "pure python + inline SVG · zero page deps"),
    ]
    stages_html = "".join(
        f'<div class="stage"><div class="sn">STAGE {sn}</div><h4>{esc(t)}</h4>'
        f'<p>{esc(d)}</p><div class="tool">{esc(tool)}</div></div>'
        for sn, t, d, tool in stages)

    agent_sec = f"""
<section id="agent"><div class="wrap">
  <div class="shead"><div class="snum">03 — THE AGENT</div>
    <h2>How 100 apps got researched without a hundred humans</h2>
    <p class="slede">A six-stage pipeline. The agent drafts, checks its own work
      against the live web, and drafts corrections - a human closes the loop.
      Total runtime on a laptop: minutes, fully re-runnable.</p>
  </div>
  {pipe_svg}
  <div class="stages">{stages_html}</div>
  <div class="callout amber"><h4>Where a human was needed - said plainly</h4>
    <ul>
      <li><b>Conflict resolution.</b> Docs, pricing pages and changelogs sometimes
        disagree (auth "deprecated but still working", MCP "announced but
        unreleased"). The agent flagged; the human decided.</li>
      <li><b>The unreadable tail.</b> A few apps ({esc("Paygent Connect, iPayX, fanbasis")})
        publish no usable public docs at all. The agent said so; the human
        confirmed it is genuinely a dead end, not a parsing failure.</li>
      <li><b>Verdict judgment.</b> "Ready with caveats" is an opinion. The agent
        proposed; the human owned the final call.</li>
      <li><b>Infra reality.</b> The provided Composio API key is rejected by the
        current v3 API (HTTP 401 - the key predates the migration), so the
        toolbelt cross-check degrades gracefully instead of guessing.</li>
    </ul></div>
</div></section>"""

    # ------------------------------------------------------------ verification
    miss_rows = []
    by2 = {a["id"]: a for a in aud2["per_app"]}
    for a in aud1["per_app"]:
        if a["all_ok"]:
            continue
        a2 = by2.get(a["id"], {"all_ok": True, "misses": []})
        for m in a["misses"]:
            f = next(x for x in a["fields"] if x["field"] == m)
            miss_rows.append(
                f'<tr><td><b>{esc(a["name"])}</b><br><span class="app-ct">'
                f'{esc(a["category"])}</span></td><td><code>{esc(m)}</code></td>'
                f'<td class="was">{esc(f["actual"]) or "—"}</td>'
                f'<td class="now">{esc(f["expected"])}</td><td><span class="fixed '
                f'{"y" if a2["all_ok"] or m not in a2["misses"] else "n"}">'
                f'{"fixed" if a2["all_ok"] or m not in a2["misses"] else "still wrong"}'
                f'</span></td></tr>')
    miss_html = ("".join(miss_rows) or
                 '<tr><td colspan="5">no misses on the audit sample</td></tr>')

    liveness = (f"Pass 1: {ver1['rows_with_live_evidence']}/{ver1['rows']} rows had "
                f"live evidence, {ver1['rows_with_dead_evidence']} dead · "
                f"Pass 2: {ver2['rows_with_live_evidence']}/{ver2['rows']} live, "
                f"{ver2['rows_with_dead_evidence']} dead")

    ver_sec = f"""
<section id="verification"><div class="wrap">
  <div class="shead"><div class="snum">04 — VERIFICATION</div>
    <h2>How we know any of this is true</h2>
    <p class="slede">Accuracy is the deliverable. Here is the loop that produced it -
      and every miss the auditor caught in the first pass, shown honestly.</p>
  </div>
  <div class="steps">
    <div class="step"><b>Draft with no web access</b>The agent drafts all 100 from
      memory. Nothing is checked yet - that is the point of pass 1.</div>
    <div class="step"><b>Check everything mechanical</b>{ver1['evidence_urls']} evidence
      URLs fetched live; rule engine flags contradictions (e.g. "no public API"
      but verdict "Ready").</div>
    <div class="step"><b>Deep-dive what was flagged</b>Fetched docs text goes to the
      LLM with a "quote or stay silent" instruction; proposals need human
      promotion.</div>
    <div class="step"><b>Audit against fixed ground truth</b>A {aud1['sample_size']}-app
      sample across all 10 categories, hand-verified with source URLs before
      grading. Same scorer grades both passes.</div>
  </div>
  <div class="acc-wrap">
    <div class="chart"><h4>Accuracy moved because of the loop</h4>
      <div class="csub">strict exact-match scoring on {aud1['sample_size']} apps ·
        {liveness}</div>
      {svg_accuracy_bars(aud1, aud2)}</div>
    <div class="chart"><h4>What the first pass got wrong
      (all {len(miss_rows)} audited misses)</h4>
      <div class="csub">draft answer → ground truth. The loop + human fixed them;
        the misses are the reason pass 2 is trustworthy.</div>
      <div style="max-height:420px;overflow:auto"><table class="miss-table">
        <thead><tr><th>App</th><th>Field</th><th>Draft said</th>
          <th>Truth</th><th>Pass 2</th></tr></thead>
        <tbody>{miss_html}</tbody></table></div></div>
  </div>
</div></section>"""

    # ------------------------------------------------------------ run
    tree = """repo/
├─ <span class="d">data/</span>            <span class="c">apps.csv roster · verified.csv (final) · overrides.csv (human ledger) · research_drafts.csv (agent proposals) · audit_sample.csv (ground truth)</span>
├─ <span class="d">src/</span>
│  ├─ agent_draft.py     <span class="c">pass 1: LLM memory-only draft (cached)</span>
│  ├─ verify.py          <span class="c">live HTTP evidence checks + rule engine</span>
│  ├─ research.py        <span class="c">deep-dive agent: fetch docs → LLM extract → proposals</span>
│  ├─ apply.py           <span class="c">draft + overrides → pass 2</span>
│  ├─ composio_check.py  <span class="c">optional Composio toolbelt cross-reference</span>
│  ├─ patterns.py        <span class="c">distributions, clusters, headline insights</span>
│  ├─ audit.py           <span class="c">strict ground-truth scoring, both passes</span>
│  ├─ render.py          <span class="c">this page, from artifacts</span>
│  └─ run_all.py         <span class="c">one command, ten stages</span>
└─ <span class="d">out/</span>             <span class="c">every intermediate artifact (JSON/CSV) - the receipts</span>"""
    run_sec = f"""
<section id="run"><div class="wrap">
  <div class="shead"><div class="snum">05 — THE PROOF</div>
    <h2>This page was generated, not written</h2>
    <p class="slede">Every artifact behind it is committed. Re-run the pipeline and
      you get the same page back; change the data and the page follows.</p>
  </div>
  <div class="two-col">
    <div>
      <div class="codeblock"><span class="cm"># full run - drafts with Gemini, verifies live</span><br>
<span class="k">git</span> clone &lt;this repo&gt; &amp;&amp; cd composio-app-research<br>
<span class="k">python</span> -m venv .venv &amp;&amp; .venv\\Scripts\\activate  <span class="cm"># (or bin/)</span><br>
<span class="k">pip</span> install -r requirements.txt<br>
<span class="k">copy</span> .env.example .env             <span class="cm"># add GEMINI_API_KEY</span><br>
<span class="k">python</span> src/run_all.py<br><br>
<span class="cm"># offline - rebuild page from committed artifacts</span><br>
<span class="k">python</span> src/run_all.py --offline</div>
      <pre class="tree">{tree}</pre>
    </div>
    <div>
      <h4 style="margin:4px 0 10px;font-size:15px">Artifacts (the receipts)</h4>
      <div class="artifacts">
        <a class="art" href="out/draft_pass1.csv"><code>draft_pass1.csv</code><span>untouched pass-1 draft</span></a>
        <a class="art" href="out/verification_pass1.json"><code>verification_pass1.json</code><span>live checks, pass 1</span></a>
        <a class="art" href="out/verification_pass2.json"><code>verification_pass2.json</code><span>live checks, pass 2</span></a>
        <a class="art" href="data/research_drafts.csv"><code>research_drafts.csv</code><span>agent proposals</span></a>
        <a class="art" href="data/overrides.csv"><code>overrides.csv</code><span>human-promoted fixes</span></a>
        <a class="art" href="out/apps_pass2.csv"><code>apps_pass2.csv</code><span>verified dataset</span></a>
        <a class="art" href="out/audit_pass1.json"><code>audit_pass1.json</code><span>audit, pass 1</span></a>
        <a class="art" href="out/audit_pass2.json"><code>audit_pass2.json</code><span>audit, pass 2</span></a>
        <a class="art" href="out/patterns.json"><code>patterns.json</code><span>computed patterns</span></a>
        <a class="art" href="out/research_report.json"><code>research_report.json</code><span>machine-readable mirror</span></a>
      </div>
      <div class="callout amber" style="margin-top:16px"><h4>Composio cross-check</h4>
        <p style="margin:0">{esc(composio.get('note') or 'not run')} -
        method: {esc(composio.get('method') or 'n/a')}
        {f'· {composio["toolkits_seen"]} toolkits seen, {len(composio.get("apps_covered", []))} of our apps covered' if composio.get('ok') else ''}</p></div>
      <div class="callout" style="background:#eef6ff;border:1px solid #cfe1ff;margin-top:16px">
        <b>Deploying the page:</b> index.html is a single static file with zero
        external dependencies - drop it on GitHub Pages / Netlify / any static
        host, or just open it from disk. It works offline.</div>
    </div>
  </div>
</div></section>"""

    # ------------------------------------------------------------ honesty
    honesty_sec = f"""
<section id="honesty"><div class="wrap">
  <div class="shead"><div class="snum">06 — HONESTY</div>
    <h2>What this research can and cannot promise</h2></div>
  <div class="honesty"><h4>Said plainly</h4><ul>
    <li><b>The audit is {aud1['sample_size']} apps, not 100.</b> The sample spans all
      categories and difficulty levels, but the remaining {100 - aud1['sample_size']} rows
      were verified by evidence-link checks and rules, not field-by-field by a human.</li>
    <li><b>Pass 2 was built with sight of the sources.</b> The human reviewer and the
      auditor used the same primary docs - the audit exists to grade the untouched
      first pass and confirm the loop's corrections, not to claim independent
      discovery. The number to trust is the delta: {pct(aud1['field_accuracy'])}
      → {pct(aud2['field_accuracy'])}.</li>
    <li><b>LLMs are nondeterministic.</b> Re-running pass 1 fresh will produce
      slightly different drafts (that is why the draft, its cache and all artifacts
      are committed). Pass 2 is deterministic: it is data + overrides.</li>
    <li><b>MCP is a moving target.</b> MCP status was checked against registries and
      vendor docs in September 2026; vendors ship servers monthly. Treat MCP="No"
      as "no at research time".</li>
    <li><b>Gating is plan-dependent.</b> "Paid self-serve" can change with pricing
      pages; where a plan changed the answer, gate_detail says how.</li>
    <li><b>What defeated us:</b> {no_api} apps with no public API, and vendor docs
      that render behind JS logins the evidence checker cannot see past. Those rows
      carry low confidence rather than invented answers.</li>
    <li><b>Verify the verifier:</b> every claim's source is one click away in the
      matrix; out/research_report.json mirrors this page for agents.</li>
  </ul></div>
</div></section>"""

    nav_html = "".join(f'<a class="nl" href="#{a}">{t}</a>' for a, t in NAV)
    page = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>100 Apps, Agent-Researched · AI Product Ops Case Study</title>
<meta name="description" content="An agent researched auth, gating, API surface and MCP status of 100 SaaS apps; a verification loop and human review pushed audit accuracy from {pct(aud1['field_accuracy'])} to {pct(aud2['field_accuracy'])}.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%23ea580c'/%3E%3Ctext x='16' y='22' font-size='16' font-family='Georgia' font-weight='bold' text-anchor='middle' fill='white'%3E100%3C/text%3E%3C/svg%3E">
<style>{CSS}</style>
</head><body>
<nav><div class="wrap"><span class="brand">app-research<span class="dot">/100</span></span>
{nav_html}<span class="spacer"></span><span class="tag">case study · {today}</span></div></nav>
{hero}
{patterns_sec}
{matrix_sec}
<script>{MATRIX_JS}</script>
{agent_sec}
{ver_sec}
{run_sec}
{honesty_sec}
<footer><div class="wrap"><span>Generated by src/render.py from pipeline artifacts ·
  draft: {esc(draft_meta.get('model', 'n/a'))} · verified {today}</span>
  <span><a href="out/research_report.json">research_report.json</a> ·
  <a href="#top">back to top</a></span></div></footer>
</body></html>"""

    INDEX_HTML.write_text(page, encoding="utf-8")
    print(f"rendered {INDEX_HTML.name} ({len(page) // 1024} KB)")


MATRIX_JS = r"""
(function(){
  var DATA = JSON.parse(document.getElementById('report-data').textContent).rows;
  var GATE_C = {"Open self-serve":"#16a34a","Paid self-serve":"#2563eb",
    "Admin approval":"#d97706","Contact sales / partner":"#dc2626",
    "N/A (no auth)":"#9ca3af"};
  var GATE_T = {"Open self-serve":"Open self-serve","Paid self-serve":"Paid self-serve",
    "Admin approval":"Admin approval","Contact sales / partner":"Sales/partner",
    "N/A (no auth)":"No auth"};
  var V_C = {"Ready":"#16a34a","Ready with caveats":"#d97706","Blocked":"#dc2626"};
  var A_C = {"OAuth2":"#ea580c","API key":"#2563eb","Basic":"#7c3aed","Token":"#0891b2",
    "HMAC":"#be185d","None":"#6b7280","Other":"#a16207"};
  var T_C = {"S":"#ea580c","A":"#2563eb","B":"#7c3aed","C":"#9ca3af"};
  var M_C = {"Yes (official)":"#ea580c","Yes (community)":"#d97706","No":"#d6d3d1",
    "Unclear":"#f5f5f4"};
  var state = {q:"",cat:"",verdict:"",mcp:"",tier:"",k:"id",dir:1};
  var cats = []; DATA.forEach(function(r){if(cats.indexOf(r.category)<0)cats.push(r.category);});
  var chipbox = document.getElementById('cats');
  cats.forEach(function(c){
    var b=document.createElement('span'); b.className='chip'; b.textContent=c; b.dataset.v=c;
    b.onclick=function(){state.cat=(state.cat===c?'':c);
      chipbox.querySelectorAll('.chip').forEach(function(x){x.classList.toggle('on',
        x.dataset.v===state.cat||(state.cat===''&&x.dataset.v===''));}); render();};
    chipbox.appendChild(b);
  });
  function chip(v){return '<span class="b" style="background:'+v.c+'">'+esc(v.t)+'</span>';}
  function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function conf(n){var s='';for(var i=1;i<=5;i++)s+='<span class="'+(i<=n?'':'off')+'">&#9679;</span>';return s;}
  function ev(r){
    var urls=(r.evidence||'').split(',').filter(Boolean);
    if(!urls.length) return '<span style="color:#d6d3d1">—</span>';
    return urls.slice(0,2).map(function(u,i){
      var st=(r.ev_status&&r.ev_status[i])||0;
      var ok=st>=200&&st<300;
      return '<a href="'+esc(u)+'" target="_blank" rel="noopener">docs ↗'+
        '<span class="st" style="color:'+(ok?'#16a34a':'#dc2626')+'">'+(st||'?')+'</span></a>';
    }).join(' ');
  }
  function rowHtml(r){
    var mcpT=r.mcp==='Yes (official)'?'MCP':(r.mcp==='Yes (community)'?'mcp':'none');
    var mcpTxt=r.mcp==='Yes (official)'?'MCP':(r.mcp==='Yes (community)'?'mcp':'—');
    return '<tr class="row" data-id="'+r.id+'">'+
    '<td class="num">'+r.id+'</td>'+
    '<td><span class="app-nm">'+esc(r.name)+'</span><br><span class="app-ct">'+
      esc(r.category)+'</span></td>'+
    '<td class="does">'+esc(r.does)+'</td>'+
    '<td>'+chip({t:r.auth,c:A_C[r.auth]||'#999'})+'</td>'+
    '<td>'+chip({t:GATE_T[r.gate]||r.gate,c:GATE_C[r.gate]||'#999'})+'</td>'+
    '<td>'+esc(r.surface)+'<div class="breadth">'+esc(r.breadth)+'</div></td>'+
    '<td>'+(r.mcp==='No'?'<span class="b ghost">none</span>':
      chip({t:mcpTxt,c:M_C[r.mcp]||'#999'}))+'</td>'+
    '<td>'+chip({t:r.tier,c:T_C[r.tier]||'#999'})+'</td>'+
    '<td>'+chip({t:r.verdict,c:V_C[r.verdict]||'#999'})+
      (r.blocker?'<div class="breadth">'+esc(r.blocker)+'</div>':'')+'</td>'+
    '<td class="ev">'+ev(r)+'</td>'+
    '<td class="conf" title="confidence '+r.confidence+'/5">'+conf(r.confidence)+'</td></tr>';
  }
  function detailHtml(r){
    function cell(k,v){return v?'<div><b>'+k+'</b>'+esc(v)+'</div>':'';}
    return '<tr class="detail"><td colspan="11"><div class="dgrid">'+
      cell('Auth detail',r.auth_detail)+cell('Gating detail',r.gate_detail)+
      cell('API breadth',r.breadth)+cell('Blocker',r.blocker)+
      '<div><b>Evidence</b><span class="evlinks">'+((r.evidence||'').split(',').
        filter(Boolean).map(function(u){return '<a href="'+esc(u)+'" target="_blank">'+
        esc(u)+'</a>';}).join('')||'—')+
        ((r.mcp_evidence)?'<a href="'+esc(r.mcp_evidence)+'" target="_blank">MCP: '+
        esc(r.mcp_evidence)+'</a>':'')+'</span></div>'+
      (r.notes?'<div><b>Notes</b><span class="note">'+esc(r.notes)+'</span></div>':'')+
      '</div></td></tr>';
  }
  var open=null;
  function render(){
    var q=state.q.toLowerCase();
    var rows=DATA.filter(function(r){
      if(state.cat&&r.category!==state.cat)return false;
      if(state.verdict&&r.verdict!==state.verdict)return false;
      if(state.mcp&&r.mcp!==state.mcp)return false;
      if(state.tier&&r.tier!==state.tier)return false;
      if(q){var hay=(r.name+' '+r.does+' '+r.auth+' '+r.auth_detail+' '+r.gate+' '+
        r.blocker+' '+r.surface+' '+r.category).toLowerCase();
        if(hay.indexOf(q)<0)return false;}
      return true;});
    rows.sort(function(a,b){var va=a[state.k],vb=b[state.k];
      if(typeof va==='number')return (va-vb)*state.dir;
      return String(va).localeCompare(String(vb))*state.dir;});
    var tb=document.getElementById('tbody'); tb.innerHTML='';
    rows.forEach(function(r){
      var tr=document.createElement('tr'); tr.innerHTML=rowHtml(r);
      tr.onclick=function(){var id=r.id;
        if(open){var prev=tb.querySelector('tr.detail');if(prev&&prev.dataset.for==id){
          prev.remove();open=null;return;}prev&&prev.remove();}
        var d=document.createElement('tr');d.className='detail';d.dataset.for=id;
        d.innerHTML=detailHtml(r);tr.after(d);open=id;};
      tb.appendChild(tr);});
    document.getElementById('count').textContent='showing '+rows.length+' of '+DATA.length;
  }
  document.getElementById('q').oninput=function(e){state.q=e.target.value;render();};
  ['fVerdict','fMcp','fTier'].forEach(function(id){
    document.getElementById(id).onchange=function(e){
      state[{fVerdict:'verdict',fMcp:'mcp',fTier:'tier'}[id]]=e.target.value;render();};});
  document.querySelectorAll('th[data-k]').forEach(function(th){
    th.onclick=function(){var k=th.dataset.k;
      state.dir=(state.k===k)?-state.dir:1;state.k=k;render();};});
  document.getElementById('csvBtn').onclick=function(){
    var cols=['id','name','category','does','auth','auth_detail','gate','gate_detail',
      'surface','breadth','mcp','verdict','blocker','evidence','tier','confidence'];
    var csv=[cols.join(',')].concat(DATA.map(function(r){
      return cols.map(function(c){return '"'+String(r[c]==null?'':r[c]).
        replace(/"/g,'""')+'"';}).join(',');})).join('\n');
    var a=document.createElement('a');
    a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));
    a.download='apps_verified.csv';a.click();};
  window.jumpTo=function(id){state.q='';document.getElementById('q').value='';
    var r=DATA.filter(function(x){return x.id===id;})[0];
    document.getElementById('fVerdict').value='';document.getElementById('fMcp').value='';
    document.getElementById('fTier').value='';state.verdict='';state.mcp='';state.tier='';
    state.cat='';
    document.querySelectorAll('#cats .chip').forEach(function(x){
      x.classList.toggle('on',x.dataset.v==='');});
    document.getElementById('tbl').scrollIntoView({behavior:'smooth'});
    setTimeout(function(){
      var tr=document.querySelector('tr.row[data-id="'+id+'"]');
      if(tr){tr.click();tr.scrollIntoView({behavior:'smooth',block:'center'});}},150);};
  render();
})();
"""

if __name__ == "__main__":
    render()
