# 100 Apps, Agent-Researched — AI Product Ops take-home

A research pipeline that profiles **100 apps** (auth method, self-serve vs gated access,
API surface + breadth, existing MCP coverage, buildability verdict, cited evidence URL),
**verifies its own claims against the live web**, and renders a single self-explanatory
case-study page: **`index.html`**.

> **Read `index.html` first** — it is the deliverable. This README is the operator manual.

## What the agent does

| Stage | Script | Output |
|---|---|---|
| 1. Knowledge core (100 validated records; 33 flagged low-confidence) | `src/knowledge*.py`, `src/analyze.py 1` | `out/apps_pass1.csv` |
| 2. Live verification loop (~500 HTTP checks: evidence fetch + auth-term confirmation, official MCP registry + Smithery lookups, docs probes) | `src/verify.py 1` | `out/verification_pass1.json` |
| 3. Pass 2: corrections from live research applied as an auditable override file | `data/overrides.csv`, `src/analyze.py 2` | `out/apps_pass2.csv` |
| 4. Re-verification of the corrected dataset | `src/verify.py 2` | `out/verification_pass2.json` |
| 5. Composio cross-check: intersect our findings with Composio's live tool catalog (v3 API) | `src/composio_check.py` | `out/composio_toolbelt.json` |
| 6. Pattern clustering (auth/gate/verdict/MCP distributions, blocker themes, pass-1→2 verdict flips, easy wins vs outreach list) | `src/patterns.py` | `out/patterns.json` |
| 7. Human-audit harness: 52 field checks against a hand-pinned ground-truth sample, computed per pass | `src/audit.py 1 / 2` | `out/audit_pass*.json` |
| 8. Case-study page (every number injected from the artifacts above) | `src/render.py` | `index.html` |

## Quickstart

```bash
python -m venv .venv
source .venv/Scripts/activate        # Windows Git Bash;  . .venv/bin/activate on unix
pip install -r requirements.txt
python src/run_all.py                # full pipeline, ~2 min, network required
```

Offline demo (skips live HTTP + Composio, rebuilds page from existing artifacts):

```bash
python src/run_all.py --skip-net
```

Individual stages: `python src/analyze.py 2`, `python src/verify.py 2`,
`python src/patterns.py`, `python src/audit.py 2`, `python src/render.py`.

## Optional: Composio cross-check (over Composio's own MCP)

The pipeline is fully keyless **except** this step. Put your key in `.env`:

```
COMPOSIO_API_KEY=ck_...
```

then `python src/composio_check.py` (or just re-run `run_all.py`). The script is a
minimal **MCP client** for `https://connect.composio.dev/mcp` (Bearer auth):
`initialize` → `notifications/initialized` → `tools/list` → per-app `tools/call` of
`COMPOSIO_SEARCH_TOOLS`. It parses the returned tool names, counts each app's
Composio toolkit, and reports the overlap with our 100 apps — an independent
"is this app agent-callable today?" oracle straight from Composio's own MCP.
Without a key the stage reports `skipped` and every other number stands on its own.

## Repo layout

```
data/apps.csv          seed list: the 100 assigned apps + category + docs hint
data/overrides.csv     pass-2 corrections (id, field, value, note) — fully auditable
data/audit_sample.csv  ground-truth sample: 52 field checks pinned to cited sources
src/                   pipeline (see table above)
out/                   every artifact: CSVs, verification reports, patterns, audits
index.html             THE deliverable — open in a browser
```

## Verification & accuracy model

- **Live loop:** every cited evidence URL is fetched (alive + does the page text mention
  the claimed auth?); every MCP claim is checked against the official MCP registry and
  Smithery; independent docs-path probes round it out. Reports: `out/verification_pass*.json`.
- **Audit:** `data/audit_sample.csv` pins expected values to cited sources *before* scoring.
  The sample deliberately includes every app the verification loop corrected, so pass-1
  accuracy (63.5%) is measured on the loop's real catch-rate; pass-2 scores 100% (52/52).
  `python src/audit.py 1` reproduces the pass-1 number.
- **No page/data drift:** `src/render.py` injects every number on the page from `out/*.json`.

## Honest limitations

- Several docs portals (developer.salesforce.com, developer.zendesk.com, clickup.com/api,
  developers.facebook.com) block non-browser clients (403/400). The citations are correct;
  the agent notes this per row and the docs were verified in a browser.
- Some docs are JS-rendered SPAs (Stripe, HubSpot, Notion): pages are alive but auth terms
  aren't extractable by a plain HTTP fetch — a disclosed agent limitation.
- MCP registry matching is heuristic (name-based) — for well-known servers only.
- The knowledge core is structured prior knowledge + targeted live research with cited
  evidence — not an autonomous LLM crawl. Every load-bearing claim is a link you can open.

## Deployment

`index.html` is fully self-contained (no external assets, works from `file://`), so any
static host works. For Vercel: push the repo to GitHub → "Add New Project" → import →
framework preset "Other" → deploy; the page is at the project root. No build step needed.
