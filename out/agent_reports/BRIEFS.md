# Agent briefs — how the research was actually conducted

Every research agent used in this case study, with its exact instructions and
scope. These briefs are committed as part of the submission: the reviewer can
compare the brief against the results in `out/agent_reports/*.json` and the
final dataset in `data/verified.csv`.

All agents ran with live web access (WebFetch / WebSearch / curl) and were
required to fetch at least one official docs page per app, report the HTTP
status they observed, and mark unverifiable fields honestly.

## Agent 1 — CRM & Support (10 apps)

Apps: Attio (4), Twenty (5), Podio (6), DealCloud (10), Close (8), Front (14),
Pylon (15), LiveAgent (16), Plain (17), Gladly (20).

Brief: for each app, fetch official developer documentation and determine
`does`, `auth` (controlled vocabulary: OAuth2 | API key | Basic | Token | HMAC |
None | Other), `gate` (Open self-serve | Paid self-serve | Admin approval |
Contact sales / partner | N/A), `surface` (Documented REST | Documented GraphQL |
REST + GraphQL | SDK/API limited | No public API), `mcp` (official | community |
No | Unclear), `verdict` (Ready | Ready with caveats | Blocked + blocker),
evidence URLs with HTTP status, and confidence 1-5. "If you could not verify
something, say so in notes and lower confidence — honesty matters more than
completeness."

Results: 10/10 fetched; highlights — DealCloud admin-gated API + official MCP,
Plain is GraphQL-only with an official MCP, Gladly is sales-led with Basic auth,
LiveAgent shipped a built-in MCP server in v5.63.

## Agent 2 — Communications & Marketing (8 apps)

Apps: Zoho Cliq (23), Lark (24), Pumble (25), Aircall (29), Vonage (30),
GoHighLevel (34), systeme.io (37), Threads (39).

Notable instruction: explain the gating in `gate_detail` (trial? paid plan?
app review?) and flag anything surprising.

Results: 8/8 fetched; highlights — systeme.io ships an official MCP (beta),
Aircall's MCP story is inverted (it consumes *your* MCP servers), Lark's docs
are a client-rendered SPA so facts were confirmed via the official GitHub org.

## Agent 3 — Ecommerce & Scraping (8 apps)

Apps: Ecwid (47), Gumroad (48), fanbasis (50), SE Ranking (52), MrScraper (54),
Sherlock (58), Waterfall.io (59), Bright Data (57).

Notable instruction: "if there is genuinely NO public API documentation, report
surface 'No public API', verdict 'Blocked', blocker 'no public API' … Honesty
matters more than completeness."

Results: found the fanbasis → Commas rebrand (beta MCP on the homepage, no
public API), Waterfall.io's genuine sales gate, MrScraper's official MCP.

## Agent 4 — Finance & AI/Media (13 apps)

Apps: Paygent Connect (84), iPayX (85), PitchBook (90), NotebookLM (91),
Otter AI (92), Fathom (93), Consensus (94), Reducto (95), Devin (96),
higgsfield (97), Mermaid CLI (98), YouTube Transcript (99), Grain (100).

Notable instruction: "search hard … if genuinely NO public API docs exist,
report it — honesty matters more than completeness."

Results: 13/13 fetched; highlights — the Paygent identity mismatch (brief said
"NMI-powered gateway"; official docs describe an AI-billing platform),
NotebookLM rebranded under Gemini Enterprise with a v1alpha API, Consensus now
API-key based (not OAuth as the brief hinted), Otter is MCP-only (no REST).

## Agent 5 — Infra & Productivity (9 apps)

Apps: Neo4j (66), Snowflake (67), MongoDB Atlas (68), Smartsheet (79),
Harvest (80), Brex (88), Ramp (89), Salesforce Commerce Cloud (44),
QuickBooks (86).

Notable instruction: focus on AUTH and GATING nuances for well-known apps
(e.g. Snowflake key-pair JWT, SCC's SLAS admin provisioning).

Results: 9/9 fetched; highlights — SFCC is genuinely Blocked (licensed
instance + admin-provisioned SLAS clients), Ramp ships llms.txt + an official
MCP, Harvest has a first-party MCP connection.

## Agent 6 — MCP officials verification (44 classifications)

Input: registry-sweep hits for 52 apps (from `src/mcp_sweep.py`).
Brief: "verify which apps ship an OFFICIAL MCP server (built/hosted by the
vendor) vs only community servers vs none … 'Yes (official)' requires
vendor-owned evidence you actually saw." Also: flag registry FALSE POSITIVES.

Results: 44 classifications with vendor evidence; 12 false positives flagged
(e.g. `com.mcparmory/*` aggregator hits, Copper's unrelated `rendex-mcp`,
Plaid's Rust UI toolkit). Curator adjustment: Amazon SP-API downgraded to
Unclear (amazon-sp-api-tools is not vendor-owned); Jira upgraded to official
with Atlassian's Remote MCP Server announcement as evidence.

## Agent 7 — MCP registry sweep (mechanical, no LLM)

`src/mcp_sweep.py` queries `registry.modelcontextprotocol.io` once per app
(100 calls, threaded) and records every hit raw: `out/mcp_sweep_raw.json`.
Used as a *floor* for community coverage; never trusted for official status.

## Deep-dive agent (in-pipeline)

`src/research.py`: for every row the verification loop flags, fetch the draft's
evidence URLs, strip scripts/nav, and ask the LLM to extract facts **strictly
from that text** with up to three verbatim quotes ("where the text is silent,
answer Unclear"). Output is a *proposal* in `data/research_drafts.csv` with
`status=draft` — never auto-applied. The quotes surfaced in the matrix detail
rows come from here, host-guarded against sources the final dataset no longer
cites.

## Draft agent (pass 1)

`src/agent_draft.py`: Gemini drafts all 100 apps in 10 batched calls with NO
web access — the deliberate, unverified baseline. Fully cached in
`out/llm_cache/`; the exact committed draft is `out/draft_pass1.csv`.
