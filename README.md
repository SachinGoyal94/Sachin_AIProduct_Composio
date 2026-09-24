# 100 Apps, Agent-Researched — AI Product Ops take-home

A research pipeline that profiles **100 apps** (auth method, self-serve vs gated access,
API surface + breadth, existing MCP coverage, buildability verdict, cited evidence URL),
**runs a live research loop** (keyless search → fetch → extract → draft corrections),
**verifies its own claims against the live web**, and renders a single self-explanatory
case-study page: **`index.html`**.

> **Read `index.html` first** — it is the deliverable. This README is the operator manual.

## What the agent does

| Stage | Script | Output |
|---|---|---|
| 1. Knowledge core (100 validated records; 33 flagged low-confidence) | `src/knowledge*.py`, `src/analyze.py 1` | `out/apps_pass1.csv` |
| 2. Live verification loop (evidence fetch + auth-term confirmation, official MCP registry + Smithery lookups, docs probes) | `src/verify.py 1` | `out/verification_pass1.json` |
| 3. **Agent research loop**: keyless web search → fetch candidate docs → extract auth/MCP/gating signals → draft corrections with source URLs | `src/research.py` | `data/research_drafts.csv` |
| 4. Human review of drafts → auditable override file | you → `data/overrides.csv` | `out/apps_pass2.csv` via `src/analyze.py 2` |
| 5. Re-verification of the corrected dataset | `src/verify.py 2` | `out/verification_pass2.json` |
| 6. Composio cross-check: intersect our findings with Composio's live tool catalog (real MCP client) | `src/composio_check.py` | `out/composio_toolbelt.json` |
| 7. Pattern clustering (auth/gate/verdict/MCP distributions, blocker themes, pass-1→2 verdict flips, easy wins vs outreach list) | `src/patterns.py` | `out/patterns.json` |
| 8. Human-audit harness: 53 field checks against a hand-pinned ground-truth sample (corrected apps + never-corrected controls), computed per pass | `src/audit.py 1 / 2` | `out/audit_pass*.json` |
| 9. Case-study page (every number injected from the artifacts above) | `src/render.py` | `index.html` |

## The research loop (`src/research.py`)

This is what makes the pipeline an *agent* rather than a fact-checker. For every app the
knowledge core flags low-confidence, it runs keyless (no LLM, no API keys):

1. **Search** — Bing HTML results, redirect URLs decoded to real targets
2. **Fetch** — top candidate doc pages, preferring official domains (name-token match against
   the domain + the app's cited evidence domain)
3. **Extract** — deterministic detectors for auth terms, MCP mentions, self-serve vs gated
   language; every hit keeps a text snippet
4. **Draft** — corrections are written to `data/research_drafts.csv` with `source_url`,
   and **never auto-applied**

The human (me) then reviews each draft against its source URL: promoted rows go into
`data/overrides.csv` (the only correction path the pipeline trusts), misreads stay in the
draft file with `status=rejected` and appear on the page — a loop that only shows its wins
isn't a verification loop. Verdict and breadth are deliberately *not* drafted; that judgment
stays human.

In the shipped run the loop made **135 HTTP requests over 33 flagged apps and drafted 10
corrections**: 4 independently reproduced fixes the human had already made, **1 was a real catch
the human pass missed** (MrScraper documents its own MCP server — promoted after verifying
`docs.mrscraper.com/docs/getting-started/mcp-server`), and 5 were rejected as misreads (e.g. an
analytics variable `amplitudeApiKey` matched as "API key"; a login-flow JS `authconfig.type ===
'oauth'` matched as OAuth2). All ten decisions are in `data/research_drafts.csv`.

## Quickstart

```bash
python -m venv .venv
source .venv/Scripts/activate        # Windows Git Bash;  . .venv/bin/activate on unix
pip install -r requirements.txt
python src/run_all.py                # full pipeline, ~4 min, network required
```

Offline demo (skips live HTTP + research + Composio, rebuilds page from existing artifacts):

```bash
python src/run_all.py --skip-net
```

Individual stages: `python src/research.py` (`--all` for all 100 apps), `python src/analyze.py 2`,
`python src/verify.py 2`, `python src/patterns.py`, `python src/audit.py 2`, `python src/render.py`.

## Optional: Composio cross-check (over Composio's own MCP)

The pipeline is fully keyless **except** this step. Put your key in `.env`:

```
COMPOSIO_API_KEY=ck_...
```

then `python src/composio_check.py` (or just re-run `run_all.py`). The script is a
minimal **MCP client** for `https://connect.composio.dev/mcp` (Bearer auth):
`initialize` → `notifications/initialized` → `tools/list` → per-app `tools/call` of
`COMPOSIO_SEARCH_TOOLS`. It parses the returned tool names, counts each app's
Composio toolkit (all 100 apps have search hints — none silently skipped), and reports
the overlap with our 100 apps — an independent
"is this app agent-callable today?" oracle straight from Composio's own MCP.
Without a key the stage reports `skipped` and every other number stands on its own.

## Repo layout

```
data/apps.csv            seed list: the 100 assigned apps + category + docs hint
data/research_drafts.csv agent-drafted corrections (id, field, value, note, source_url, status)
data/overrides.csv       human-reviewed corrections (id, field, value, note) — fully auditable
data/audit_sample.csv    ground-truth sample: 53 field checks pinned to cited sources
src/                     pipeline (see table above)
out/                     every artifact: CSVs, verification reports, patterns, audits
index.html               THE deliverable — open in a browser
```

## Verification & accuracy model

- **Live loop:** every cited evidence URL is fetched (alive + does the page text mention
  the claimed auth?); every MCP *Yes* claim is checked against the official MCP registry and
  Smithery and reported as confirmed/unconfirmed (No-claims are excluded, not auto-passed);
  independent docs-path probes round it out. Reports: `out/verification_pass*.json`.
- **Research loop:** `research.py` re-derives flagged rows from live pages; its agreement
  and disagreements with the shipped dataset are computed and shown on the page.
- **Audit:** `data/audit_sample.csv` pins expected values to cited sources *before* scoring.
  The 53 checks span 41 apps — every app the loop corrected **plus 18 never-corrected
  controls** — so pass-1 accuracy (62.3%) is measured on the loop's real catch-rate and
  pass-2 scores 100% (53/53) including controls. `python src/audit.py 1` reproduces the
  pass-1 number.
- **No page/data drift:** `src/render.py` injects every number on the page from
  `out/*.json` + `data/*.csv` — there are no hardcoded counts in the template.

## Honest limitations

- Several docs portals (developer.salesforce.com, developer.zendesk.com, clickup.com/api,
  developers.facebook.com) block non-browser clients (403/400). The citations are correct;
  the agent notes this per row and the docs were verified in a browser.
- Some docs are JS-rendered SPAs (Stripe, HubSpot, Notion): pages are alive but auth terms
  aren't extractable by a plain HTTP fetch — a disclosed agent limitation.
- The research loop's extractors are regex-based, not LLM reads — so its drafts get human
  review, and rejected drafts stay visible in `data/research_drafts.csv` and on the page.
- MCP registry matching is heuristic (name-based) — for well-known servers only.
- The knowledge core is structured prior knowledge + targeted live research with cited
  evidence. Every load-bearing claim is a link you can open.

## Deployment

`index.html` is fully self-contained (no external assets, works from `file://`), so any
static host works. For Vercel: push the repo to GitHub → "Add New Project" → import →
framework preset "Other" → deploy; the page is at the project root. No build step needed.
