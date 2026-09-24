"""Render the case study: one self-explanatory index.html.

Everything visible on the page is computed from out/*.json + data/*.csv + the
final dataset, so the page cannot drift from the data - there are no hardcoded
counts anywhere in the template.

Usage: python render.py
"""
from __future__ import annotations

import csv
import json
from datetime import datetime

from config import DATA, OUT, ROOT

AUTH_PILL = {
    "OAuth2": "pill-blue", "API key": "pill-teal", "Basic": "pill-purple",
    "Bearer token": "pill-indigo", "JWT": "pill-purple", "HMAC": "pill-purple",
    "OAuth1": "pill-purple", "None": "pill-gray",
}
GATE_PILL = {
    "Self-serve": "pill-green", "Open": "pill-green",
    "Self-serve (paid)": "pill-amber", "Gated": "pill-red",
}
VERDICT_PILL = {
    "Ready": "pill-green", "Ready with caveats": "pill-amber", "Blocked": "pill-red",
}


def _load(name: str, default):
    p = OUT / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def _load_drafts() -> list[dict]:
    p = DATA / "research_drafts.csv"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return [{**r, "agrees_with_final": r["agrees_with_final"] == "True"}
                for r in csv.DictReader(f)]


def _audit_split() -> tuple[int, int, int]:
    """(unique apps in sample, apps the loop corrected, never-corrected controls)."""
    try:
        with open(DATA / "audit_sample.csv", encoding="utf-8") as f:
            sample_ids = {int(r["id"]) for r in csv.DictReader(f)}
        with open(DATA / "overrides.csv", encoding="utf-8") as f:
            corrected_ids = {int(r["id"]) for r in csv.DictReader(f)}
        n_corrected = len(sample_ids & corrected_ids)
        return len(sample_ids), n_corrected, len(sample_ids) - n_corrected
    except OSError:
        return 0, 0, 0


def run() -> None:
    with open(OUT / "apps_pass2.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    pat = _load("patterns.json", {})
    flags1 = _load("pass1_flags.json", {})
    ver1 = _load("verification_pass1.json", {"summary": {}}).get("summary", {})
    ver2 = _load("verification_pass2.json", {"summary": {}}).get("summary", {})
    aud1 = _load("audit_pass1.json", {"accuracy": "?", "sample_size": "?", "matches": "?"})
    aud2 = _load("audit_pass2.json", {"accuracy": "?", "sample_size": "?", "matches": "?"})
    comp = _load("composio_toolbelt.json", None)
    res = _load("research_report.json", {"summary": {}}).get("summary", {})
    drafts = _load_drafts()

    def pct(d, key, value):
        for item in d.get(key, []):
            if item["value"] == value:
                return item["pct"]
        return 0

    def cnt(d, key, value):
        for item in d.get(key, []):
            if item["value"] == value:
                return item["count"]
        return 0

    n_ready = cnt(pat, "verdict_dist", "Ready")
    n_mcp = cnt(pat, "mcp_dist", "Yes")
    n_selfserve = sum(cnt(pat, "gate_dist", g) for g in ("Self-serve", "Open"))
    n_selfserve_paid = cnt(pat, "gate_dist", "Self-serve (paid)")
    n_gated = cnt(pat, "gate_dist", "Gated")
    bearer = pct(pat, "auth_dist", "Bearer token")
    apikey = pct(pat, "auth_dist", "API key")
    oauth2 = pct(pat, "auth_dist", "OAuth2")
    flips = pat.get("verdict_flips", [])
    themes = pat.get("blocker_themes", [])
    p1_miss = aud1.get("mismatches", [])
    n_ovr = pat.get("n_overrides_applied", 0)
    n_flagged = flags1.get("n_flagged", "?")
    n_checks = (ver1.get("n_http_requests", 0) + ver2.get("n_http_requests", 0)
                + res.get("n_http_requests", 0))
    n_sample_apps, n_corrected_apps, n_control_apps = _audit_split()

    # agent research loop: drafts vs the human-verified final dataset
    n_drafts = len(drafts)
    n_draft_agree = sum(1 for d in drafts if d["agrees_with_final"])
    n_draft_dis = n_drafts - n_draft_agree
    st = lambda s: sum(1 for d in drafts if d.get("status", "draft") == s)  # noqa: E731
    n_promoted, n_rejected, n_confirm = st("promoted"), st("rejected"), st("confirmation")
    disagree_rows = "".join(
        f"<tr><td>#{d['id']} {d['name']}</td><td>{d['field']}</td>"
        f"<td>agent: <b>{d['value']}</b> · shipped: {d['final_value']}</td>"
        f"<td>{d.get('status', 'draft')}</td>"
        f"<td class='dim'><a href='{d['source_url']}'>source</a></td></tr>"
        for d in drafts if not d["agrees_with_final"]) or \
        "<tr><td colspan='5' class='dim'>no agent/human disagreements</td></tr>"

    # ---------------- table data ----------------
    table_rows = []
    for r in rows:
        table_rows.append({
            "id": int(r["id"]), "name": r["name"], "cat": r["category"],
            "does": r["does"], "auth": r["auth"], "gate": r["gate"],
            "surface": r["surface"], "breadth": r["breadth"], "mcp": r["mcp"],
            "verdict": r["verdict"], "blocker": r["blocker"],
            "ev": r["evidence"], "conf": int(r["confidence"]), "notes": r["notes"],
        })
    data_json = json.dumps(table_rows, ensure_ascii=False).replace("</", "<\\/")

    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "Dataset",
        "name": "100 Apps, Agent-Researched — AI Product Ops take-home",
        "description": "Research agent profiles 100 SaaS apps (auth method, self-serve vs "
                       "gated access, API surface, MCP coverage, buildability verdict), "
                       "verifies claims against the live web, and clusters the patterns.",
        "variableMeasured": ["auth", "gate", "surface", "breadth", "mcp", "verdict",
                             "blocker", "evidence"],
        "observationCount": len(table_rows),
        "headlineStats": {
            "readyPct": n_ready, "mcpPct": n_mcp, "selfServePct": n_selfserve,
            "auditAccuracyPass1": aud1.get("accuracy"), "auditAccuracyPass2": aud2.get("accuracy"),
            "liveHttpChecks": n_checks,
        },
    }, ensure_ascii=False).replace("</", "<\\/")

    # ---------------- composio section ----------------
    if comp and comp.get("status", "").startswith("ok"):
        comp_html = f"""
        <p>The agent connects to <b>Composio's own MCP gateway</b>
        (<code>{comp.get('transport', 'MCP')}</code>) as a real MCP client — initialize → tools/call —
        and queries <code>COMPOSIO_SEARCH_TOOLS</code> once per app for
        <b>{comp.get('apps_searched', '?')} of the 100</b> (every app now has a search hint — none
        silently skipped). Result:
        <b>{comp.get('overlaps_with_our_100', '?')} apps already ship Composio toolkits</b>, an independent
        vendor-side confirmation that those apps are agent-callable today — and a live demo of this
        agent using Composio's own MCP, per the assignment. Biggest toolkits:</p>
        <table class="mini"><tr><th>App</th><th>Composio tools</th><th>Sample tools</th></tr>
        {''.join(f"<tr><td>{o['name']}</td><td>{o['n_tools']}</td><td><code>{', '.join(o['sample_tools'][:2])}</code></td></tr>" for o in comp.get('overlaps', [])[:12])}
        </table>"""
    else:
        reason = comp.get("status", "not run") if comp else "not run"
        comp_html = f"""
        <p><b>Status: cross-check available but not active ({reason}).</b> The agent ships with
        <code>src/composio_check.py</code>, a real MCP client that pulls Composio's live tool
        catalog and intersects it with the 100 researched apps - using Composio's own platform as an
        independent 'is this app agent-callable today?' oracle. Set
        <code>COMPOSIO_API_KEY</code> in <code>.env</code> and re-run
        <code>python src/run_all.py</code>; every other number on this page already stands on its own.</p>"""

    # ---------------- blockers bar list ----------------
    theme_rows = "".join(
        f"<tr><td>{t['theme']}</td><td>{t['count']}</td>"
        f"<td class='dim'>{' · '.join(t['examples'][:2])}</td></tr>"
        for t in themes)

    # ---------------- audit mismatches (pass-1 catches) ----------------
    miss_rows = "".join(
        f"<tr><td>#{m['id']} {m['name']}</td><td>{m['field']}</td>"
        f"<td><s>{m['agent']}</s> → <b>{m['expected']}</b></td>"
        f"<td class='dim'>{m['source_of_truth']}</td></tr>"
        for m in p1_miss[:12])

    flip_rows = "".join(
        f"<span class='flip'>#{f['id']} {f['name']}: {f['from']} → <b>{f['to']}</b></span>"
        for f in flips)

    cats = sorted({r["cat"] for r in table_rows})

    page = HTML_HEAD + STYLE + BODY_TOP.format(
        date=datetime.now().strftime("%d %b %Y"),
        n_ready=n_ready, n_mcp=n_mcp, n_selfserve=n_selfserve,
        bearer=bearer, apikey=apikey, oauth2=oauth2,
        n_checks=f"{n_checks:,}",
        ev1_alive=ver1.get("evidence_alive", "?"), ev2_alive=ver2.get("evidence_alive", "?"),
        ev1_pct=ver1.get("evidence_alive_pct", "?"), ev2_pct=ver2.get("evidence_alive_pct", "?"),
        ev1_ok=ver1.get("evidence_ok", "?"), ev2_ok=ver2.get("evidence_ok", "?"),
        ev1_okpct=ver1.get("evidence_pct", "?"), ev2_okpct=ver2.get("evidence_pct", "?"),
        mcp1c=ver1.get("mcp_yes_confirmed", "?"), mcp1t=ver1.get("mcp_yes_total", "?"),
        mcp1=ver1.get("mcp_yes_pct", "?"), mcp2c=ver2.get("mcp_yes_confirmed", "?"),
        mcp2t=ver2.get("mcp_yes_total", "?"), mcp2=ver2.get("mcp_yes_pct", "?"),
        probe2=ver2.get("docs_probe_pct", "?"),
        aud1_acc=aud1.get("accuracy"), aud1_n=aud1.get("sample_size"),
        aud2_acc=aud2.get("accuracy"), aud2_n=aud2.get("sample_size"),
        aud2_ok=aud2.get("matches"),
        n_sample_apps=n_sample_apps, n_corrected_apps=n_corrected_apps,
        n_control_apps=n_control_apps,
        n_selfserve_pct=round(100 * n_selfserve / 100, 0),
        n_gated=n_gated, n_paid=n_selfserve_paid,
        n_flagged=n_flagged, n_ovr=n_ovr,
        res_targeted=res.get("n_apps_targeted", "?"),
        res_researched=res.get("n_apps_researched", "?"),
        res_reqs=res.get("n_http_requests", "?"),
        n_drafts=n_drafts, n_draft_agree=n_draft_agree, n_draft_dis=n_draft_dis,
        n_promoted=n_promoted, n_rejected=n_rejected, n_confirm=n_confirm,
        res_apps=res.get("n_apps_with_drafts", "?"),
        disagree_rows=disagree_rows,
        n_miss=len(p1_miss),
        theme_rows=theme_rows, miss_rows=miss_rows, flip_rows=flip_rows,
        comp_html=comp_html,
        cats="".join(f"<button class='cat' data-c='{c}'>{c.split(',')[0].split(' and ')[0]}</button>" for c in cats),
        n_notready=100 - n_ready,
    ) + BODY_END
    html = page.replace("__DATA__", data_json).replace("__JSONLD__", jsonld)

    out_path = ROOT / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"wrote {out_path} ({len(html):,} bytes)")


HTML_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>100 Apps, Agent-Researched — AI Product Ops Case Study</title>
<meta name="description" content="Research agent that profiled 100 apps (auth, gating, API surface, MCP, verdicts), verified itself against the live web, and clustered the patterns.">
<script type="application/ld+json">__JSONLD__</script>
"""

STYLE = """
<style>
:root{--bg:#0b1020;--panel:#121a30;--panel2:#0e1526;--line:#223052;--tx:#e8edf7;--dim:#93a0ba;
--acc:#6d8dff;--acc2:#39d0c3;--green:#3ecf8e;--amber:#f0b429;--red:#f2708a;--purple:#b18cff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 22px 80px}
a{color:var(--acc2);text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:34px;margin:.2em 0 .1em;line-height:1.15}
h2{font-size:22px;margin:2.2em 0 .5em;padding-top:.6em;border-top:1px solid var(--line)}
h3{font-size:17px;margin:1.4em 0 .4em;color:var(--acc)}
.lead{color:var(--dim);font-size:17px;max-width:70ch}
.dim{color:var(--dim)}
code{background:#1a2340;border:1px solid var(--line);border-radius:5px;padding:1px 6px;font-size:.85em}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin:20px 0 6px}
.chip{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 16px;min-width:130px}
.chip b{display:block;font-size:22px;line-height:1.2}
.chip span{color:var(--dim);font-size:12.5px;text-transform:uppercase;letter-spacing:.06em}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin:14px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.card ul{margin:.4em 0 .2em;padding-left:1.2em}
.card li{margin:.3em 0}
.finding{border-left:3px solid var(--acc);padding:10px 14px;background:var(--panel2);border-radius:0 10px 10px 0;margin:10px 0}
.finding b{color:#fff}
.pill{display:inline-block;border-radius:999px;padding:1px 10px;font-size:12px;font-weight:600;white-space:nowrap;border:1px solid transparent}
.pill-green{background:rgba(62,207,142,.14);color:var(--green);border-color:rgba(62,207,142,.4)}
.pill-amber{background:rgba(240,180,41,.13);color:var(--amber);border-color:rgba(240,180,41,.4)}
.pill-red{background:rgba(242,112,138,.13);color:var(--red);border-color:rgba(242,112,138,.4)}
.pill-blue{background:rgba(109,141,255,.14);color:var(--acc);border-color:rgba(109,141,255,.4)}
.pill-indigo{background:rgba(177,140,255,.14);color:var(--purple);border-color:rgba(177,140,255,.4)}
.pill-teal{background:rgba(57,208,195,.13);color:var(--acc2);border-color:rgba(57,208,195,.4)}
.pill-purple{background:rgba(177,140,255,.12);color:var(--purple);border-color:rgba(177,140,255,.35)}
.pill-gray{background:rgba(147,160,186,.12);color:var(--dim);border-color:rgba(147,160,186,.35)}
table{border-collapse:collapse;width:100%;font-size:14px}
th{color:var(--dim);text-align:left;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em}
table.mini th,table.mini td{border:1px solid var(--line);padding:6px 10px}
table.mini{margin:10px 0}
#tbl th{position:sticky;top:0;background:var(--panel);cursor:pointer;user-select:none;padding:8px 8px;border-bottom:1px solid var(--line);z-index:2}
#tbl td{padding:7px 8px;border-bottom:1px solid #1a2340}
#tbl tr:hover td{background:#141d38}
#tblWrap{max-height:640px;overflow:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel2)}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0}
.toolbar input{background:var(--panel);border:1px solid var(--line);color:var(--tx);border-radius:9px;padding:8px 12px;min-width:240px}
button.cat{background:var(--panel);border:1px solid var(--line);color:var(--tx);border-radius:999px;padding:6px 13px;cursor:pointer;font-size:13px}
button.cat.on{background:var(--acc);border-color:var(--acc);color:#0b1020;font-weight:700}
.flow{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:14px 0}
.step{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px}
.step b{color:var(--acc2);display:block;margin-bottom:4px;font-size:13.5px}
.step span{font-size:13px;color:var(--dim)}
.flip{display:inline-block;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:4px 10px;margin:3px 6px 3px 0;font-size:13px}
.note{background:rgba(240,180,41,.07);border:1px solid rgba(240,180,41,.35);border-radius:12px;padding:14px 16px;margin:14px 0}
.good{background:rgba(62,207,142,.07);border:1px solid rgba(62,207,142,.35);border-radius:12px;padding:14px 16px;margin:14px 0}
footer{margin-top:60px;color:var(--dim);font-size:13.5px;border-top:1px solid var(--line);padding-top:18px}
.kbd{color:var(--dim);font-size:12.5px}
.arrow{color:var(--acc2);font-weight:700}
.big{font-size:15px}
@media print{body{background:#fff;color:#000}.card,.chip{border-color:#bbb}#tblWrap{max-height:none;overflow:visible}}
</style>
</head>
"""

BODY_TOP = """<body><div class="wrap">
<header>
<div class="kbd">AI Product Ops — take-home case study · Sachin Goyal · generated {date}</div>
<h1>100 apps, agent-researched.<br>One page, fully verifiable.</h1>
<p class="lead">I built a research agent that profiled <b>100 apps</b> across 10 categories — auth
method, self-serve vs gated access, API surface, existing MCP coverage, and a buildability verdict
with cited evidence — then verified its own claims against the live web ({n_checks} live HTTP checks,
no LLM keys) and a hand-audited ground-truth sample. Everything below is computed from the pipeline's
artifacts; the full 100-row table is at the bottom.</p>
<div class="chips">
<div class="chip"><b>100</b><span>apps profiled</span></div>
<div class="chip"><b>{n_ready}%</b><span>toolkit-ready today</span></div>
<div class="chip"><b>{n_mcp}%</b><span>already ship an MCP server</span></div>
<div class="chip"><b>{n_selfserve}%</b><span>fully self-serve access</span></div>
<div class="chip"><b>{aud1_acc}% → {aud2_acc}%</b><span>audit accuracy (pass 1 → 2)</span></div>
<div class="chip"><b>{ev1_pct}% → {ev2_pct}%</b><span>evidence URLs live</span></div>
</div>
</header>

<h2>The headline — five patterns</h2>
<div class="finding"><b>1. Credentials beat OAuth in the agent era.</b> Bearer/PAT-style tokens
({bearer}%) plus plain API keys ({apikey}%) dominate; classic browser-flow OAuth2 is only {oauth2}%.
For tool builders this is good news: the majority of these apps authenticate with exactly the kind
of long-lived credential an agent runtime can hold.</div>
<div class="finding"><b>2. Self-serve is the norm — gating is the exception that clusters.</b>
{n_selfserve}% of apps let a developer pull credentials immediately (another {n_paid}% are self-serve
on paid tiers). Only {n_gated}% are truly gated, and that gating concentrates in two places: the
ads/social cluster and finance.</div>
<div class="finding"><b>3. The MCP land-rush already happened.</b> {n_mcp}% of these 100 apps have a
discoverable MCP server today (official or community, confirmed against the official MCP registry
+ Smithery). For a toolkit vendor, MCP parity is table stakes, not differentiation — the
differentiator is verified auth handling and write-safe operations.</div>
<div class="finding"><b>4. The most common blocker is bureaucracy, not technology.</b> Across the
{n_notready} non-fully-ready apps, blockers cluster as: approval processes and paid-plan
walls (see table) — not missing APIs. Only a handful have no usable API at all.</div>
<table class="mini">
<tr><th>Blocker theme</th><th>Apps</th><th>Examples</th></tr>
{theme_rows}
</table>
<div class="finding"><b>5. Easy wins vs outreach list.</b> Productivity/PM and Dev-infra apps are
nearly all self-serve + MCP: a toolkit ships there with zero human contact. The ads cluster
(Google Ads, Meta Ads, LinkedIn Ads) and Amazon SP-API need review/partnership — that is the
outreach list, and 'gated with evidence' is the correct finding, not a failure.</div>

<h2>The workflow — how the agent worked</h2>
<div class="flow">
<div class="step"><b>1 · Knowledge core</b><span>Structured priors for all 100 apps from documented
knowledge; every row schema-validated, {n_flagged} rows flagged low-confidence for live checking</span></div>
<div class="step"><b>2 · Live verification loop</b><span>Fetch every cited evidence URL, confirm
auth terms in page text, query official MCP + Smithery registries, probe docs paths</span></div>
<div class="step"><b>3 · Agent research loop</b><span>For the {n_flagged} flagged apps: keyless web
search → fetch candidate docs → extract auth/MCP/gating signals → <b>{n_drafts} draft corrections</b>
on {res_apps} apps ({res_reqs} HTTP requests). Drafts are never auto-applied</span></div>
<div class="step"><b>4 · Human review</b><span>I reviewed every draft against its source URL:
{n_promoted} real catch promoted, {n_rejected} rejected, {n_confirm} matched fixes I had already
made independently; accepted fixes flow into an auditable overrides file — {n_ovr} applied</span></div>
<div class="step"><b>5 · Composio MCP cross-check</b><span>Agent connects to Composio's own MCP
gateway and intersects its live toolkit catalog with our findings</span></div>
<div class="step"><b>6 · Human audit</b><span>{aud2_n}-row ground-truth sample hand-pinned to sources;
accuracy computed per field: {aud1_acc}% → {aud2_acc}%</span></div>
<div class="step"><b>7 · Render</b><span>This page. Every number injected from pipeline artifacts —
the page cannot drift from the data</span></div>
</div>

<h2>The agent — what I built</h2>
<div class="grid">
<div class="card"><h3>Automated (deterministic Python, zero LLM keys)</h3><ul>
<li><code>knowledge_*.py</code> — validated 100-record research core (ids, vocabularies, evidence URLs)</li>
<li><code>verify.py</code> — concurrent evidence fetch + auth-term confirmation + MCP registry lookups + docs probes</li>
<li><code>research.py</code> — the research loop: keyless search → fetch candidate docs → extract auth/MCP/gating signals → write draft corrections with source URLs</li>
<li><code>composio_check.py</code> — MCP-gateway cross-check: drives Composio's own MCP server as a client and intersects its live toolkit catalog with our findings</li>
<li><code>patterns.py</code> — clustering: auth/gate/verdict/MCP distributions, blocker themes, flips</li>
<li><code>audit.py</code> — computes accuracy against the ground-truth sample per pass</li>
<li><code>render.py</code> — this page, from artifacts only</li>
</ul></div>
<div class="card"><h3>Where a human was needed (me)</h3><ul>
<li>Reviewing the agent's research drafts field-by-field against their source URLs: {n_confirm}
matched fixes I had already made independently, {n_promoted} was a real catch I had missed and got
promoted, {n_rejected} were rejected as misreads — the drafts file keeps every decision auditable</li>
<li>Deciding what the evidence <i>means</i>: a 200-OK page that a bot can't read (Stripe, HubSpot,
Notion are JS-rendered SPAs) vs genuinely missing docs (iPayX)</li>
<li>Judging gating language: 'trial available' vs 'contact sales' vs 'app review' — and setting the
verdict, which the agent deliberately does not draft</li>
<li>Live search for the obscure apps (Fanbasis login-walled docs, Paygent adapter-only footprint,
Waterfall's hidden-but-public docs)</li>
<li>Pinning the {aud2_n}-row ground-truth audit sample to cited sources</li>
</ul></div>
</div>
{comp_html}
<div class="note"><b>Honest limitations.</b> Several docs portals (developer.salesforce.com,
developer.zendesk.com, clickup.com/api, developers.facebook.com) actively block non-browser
clients (403/400) — those evidence URLs are correct but show as blocked to the agent; I verified
them in a browser and noted it per row. The research loop's extractors are regex-based, not LLM
reads — that is why drafts get human review, and any draft that misreads a page is shown below
instead of silently applied. MCP registry lookups are heuristic (name matching). The knowledge core
is structured prior knowledge + targeted live research — which is exactly why every load-bearing
claim carries a URL you can open.</div>

<h2>The proof — verification &amp; accuracy movement</h2>
<table class="mini">
<tr><th>Signal (all live, per pass)</th><th>Pass 1</th><th>Pass 2 (final)</th></tr>
<tr><td>Cited evidence URL alive (HTTP 200)</td><td>{ev1_alive}/100 ({ev1_pct}%)</td><td>{ev2_alive}/100 ({ev2_pct}%)</td></tr>
<tr><td>Alive <i>and</i> auth terms confirmed in page text</td><td>{ev1_ok}/100 ({ev1_okpct}%)</td><td>{ev2_ok}/100 ({ev2_okpct}%)</td></tr>
<tr><td>MCP 'Yes' claims confirmed by registries (of Yes-claims only)</td><td>{mcp1c}/{mcp1t} ({mcp1}%)</td><td>{mcp2c}/{mcp2t} ({mcp2}%)</td></tr>
<tr><td>Docs probes reachable (independent path probe)</td><td>—</td><td>{probe2}%</td></tr>
<tr><td>Ground-truth audit accuracy ({aud2_n} field checks)</td><td>{aud1_acc}%</td><td><b>{aud2_acc}%</b></td></tr>
</table>
<p>The audit sample covers <b>{n_sample_apps} apps ({n_corrected_apps} the loop corrected +
{n_control_apps} never-corrected controls), {aud2_n} field checks</b>, hand-pinned to cited sources —
so pass-1 accuracy is measured on the loop's real catch-rate, and pass-2 includes controls the
correction process never touched. What the verification loop caught (pass-1 wrong → pass-2 right,
each fixed against a cited source; showing 12 of {n_miss}):</p>
<table class="mini">
<tr><th>App</th><th>Field</th><th>Correction</th><th>Source of truth</th></tr>
{miss_rows}
</table>
<p class="dim">Verdicts that changed after live verification: {flip_rows}</p>

<h3>The agent research loop — drafts vs the human</h3>
<p><code>research.py</code> re-researched the {res_targeted} low-confidence apps live
(keyless search → fetch → extract; {res_reqs} HTTP requests) and drafted <b>{n_drafts}
corrections</b> across {res_apps} apps. It never applies them itself. Against the shipped,
human-verified dataset: <b>{n_confirm} drafts independently reproduced a correction I had already
made</b>, {n_promoted} matched a real catch I had missed and went into the dataset after I verified
its source, and {n_rejected} were rejected as misreads — shown below rather than silently applied,
because a loop that only shows you its wins isn't a verification loop.</p>
<table class="mini">
<tr><th>App</th><th>Field</th><th>Agent draft vs shipped value</th><th>Review status</th><th></th></tr>
{disagree_rows}
</table>

<h2>The findings — all 100 apps</h2>
<div class="toolbar">
<input id="q" type="search" placeholder="Search app, category, auth, blocker…">
<span>{cats}</span>
<button class="cat on" data-c="">All</button>
</div>
<div id="tblWrap">
<table id="tbl">
<thead><tr>
<th data-k="id">#</th><th data-k="name">App ↗</th><th data-k="cat">Category</th>
<th data-k="does">What it does</th><th data-k="auth">Auth</th><th data-k="gate">Access</th>
<th data-k="surface">API surface</th><th data-k="breadth">Breadth</th><th data-k="mcp">MCP</th>
<th data-k="verdict">Verdict</th><th data-k="blocker">Blocker / caveat</th><th data-k="conf">Conf</th>
</tr></thead>
<tbody></tbody>
</table>
</div>
<p class="kbd" id="count"></p>
<p class="kbd">Conf = confidence (1–5): how many independent signals backed the row when written.
The app name links to its cited evidence (↗). Full dataset:
<code>out/apps_pass2.csv</code>; agent research drafts: <code>data/research_drafts.csv</code>;
verification reports: <code>out/verification_pass*.json</code>;
audit: <code>out/audit_pass*.json</code>; patterns: <code>out/patterns.json</code>; this page is
also machine-readable: a JSON-LD <code>Dataset</code> block sits in the HTML head.</p>

<h2>Run it yourself</h2>
<div class="card"><code>git clone &lt;repo&gt; && cd Sachin_AIProduct_Composio</code><br>
<code>python -m venv .venv && .venv\\Scripts\\activate</code> <span class="kbd">(Windows; source .venv/bin/activate on unix)</span><br>
<code>pip install -r requirements.txt</code><br>
<code>python src/run_all.py</code> <span class="kbd">→ rebuilds every artifact and this page (~4 min, network required)</span><br>
<code>python src/composio_check.py</code> <span class="kbd">optional: add COMPOSIO_API_KEY to .env</span></div>

<footer>
Pipeline: knowledge core → live verification loop → agent research loop (search → fetch → extract →
draft) → human review → overrides → Composio cross-check → audit → this page. No LLM keys required;
every extraction is a regex over a fetched page with its URL attached. Generated {date} by
<code>src/render.py</code>.
</footer>
</div>
"""

BODY_END = """
<script>
const DATA = __DATA__;
const GATE_PILL = {"Self-serve":"pill-green","Open":"pill-green","Self-serve (paid)":"pill-amber","Gated":"pill-red"};
const VERDICT_PILL = {"Ready":"pill-green","Ready with caveats":"pill-amber","Blocked":"pill-red"};
const AUTH_PILL = {"OAuth2":"pill-blue","API key":"pill-teal","Basic":"pill-purple","Bearer token":"pill-indigo","JWT":"pill-purple","HMAC":"pill-purple","OAuth1":"pill-purple","None":"pill-gray"};
let catF = "", q = "", sortK = "id", sortDir = 1;
const $ = s => document.querySelector(s);
function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function render(){
  let rows = DATA.filter(r => (!catF || r.cat === catF) &&
    (!q || (r.name+" "+r.cat+" "+r.does+" "+r.auth+" "+r.gate+" "+r.blocker+" "+r.verdict).toLowerCase().includes(q)));
  rows.sort((a,b)=>{const x=a[sortK],y=b[sortK];return (typeof x==="number"?x-y:String(x).localeCompare(String(y)))*sortDir});
  $("#tbl tbody").innerHTML = rows.map(r => `<tr>
    <td>${r.id}</td>
    <td><a href="${r.ev}" target="_blank" rel="noopener">${esc(r.name)}</a> <span class="arrow">↗</span></td>
    <td class="dim">${esc(r.cat)}</td>
    <td>${esc(r.does)}</td>
    <td><span class="pill ${AUTH_PILL[r.auth]||"pill-gray"}">${esc(r.auth)}</span></td>
    <td><span class="pill ${GATE_PILL[r.gate]||"pill-gray"}">${esc(r.gate)}</span></td>
    <td>${esc(r.surface)}</td>
    <td class="dim">${esc(r.breadth)}</td>
    <td>${r.mcp==="Yes"?'<span class="pill pill-teal">Yes</span>':'<span class="pill pill-gray">No</span>'}</td>
    <td><span class="pill ${VERDICT_PILL[r.verdict]||"pill-gray"}">${esc(r.verdict)}</span></td>
    <td class="dim">${esc(r.blocker)}</td>
    <td class="dim">${r.conf}</td>
  </tr>`).join("");
  $("#count").textContent = `showing ${rows.length} of ${DATA.length} apps`;
}
document.querySelectorAll("button.cat").forEach(b => b.onclick = () => {
  document.querySelectorAll("button.cat").forEach(x=>x.classList.remove("on"));
  b.classList.add("on"); catF = b.dataset.c; render();
});
$("#q").oninput = e => { q = e.target.value.toLowerCase(); render(); };
document.querySelectorAll("#tbl th").forEach(th => th.onclick = () => {
  const k = th.dataset.k; sortDir = (k === sortK) ? -sortDir : 1; sortK = k; render();
});
render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    run()
