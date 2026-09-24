# app-research/100 — agent-researched API integration landscape

> **Live case study: <https://ai-product-sachin.vercel.app>**
>
> One agent + one verification loop researched **100 SaaS apps across 10
> categories**: auth methods, self-serve vs gated credential access, API
> surface, MCP (Model Context Protocol) coverage, and a buildability verdict —
> with an evidence URL behind every row and an audited accuracy trail.

Built as a take-home case study for Composio's AI Product Ops role.
**Open the live link, or `index.html` locally** — the whole case study is one
self-explanatory page (headline result: strict ground-truth audit accuracy
moved from **70% to 100%** between the untouched first pass and the verified
dataset; every miss the auditor caught in pass 1 is listed on the page).

## How to run the research agent

```bash
git clone <this repo> && cd <repo>
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # add GEMINI_API_KEY; optionally set GEMINI_MODEL
python src/run_all.py       # full run: 14 stages, a few minutes
```

Offline (rebuild the page from committed artifacts, no network, no key):

```bash
python src/run_all.py --offline
```

The draft model is whatever `GEMINI_MODEL` says (default
`gemini-3.5-flash-lite`); every Gemini call is cached on disk under
`out/llm_cache/`, so re-runs are reproducible and cheap.

## What the pipeline does

`python src/run_all.py` executes 14 stages:

| Stage | Script | What happens |
|---|---|---|
| 1. Pass 1 — draft | `src/agent_draft.py` | The LLM drafts all 100 apps **from memory only** (batched, cached). The honest, unverified first pass. |
| 2. Verify | `src/verify.py 1` | Fetches every evidence URL live (status, redirects, auth-keyword sniffing) + a contradiction/vocabulary rule engine. |
| 3. Deep-dive | `src/research.py` | For flagged rows: fetch real docs pages, LLM extracts facts **strictly from that text** with verbatim quotes → proposals. |
| 4. MCP sweep | `src/mcp_sweep.py` | Queries the official MCP registry for every app (mechanical evidence, committed raw). |
| 5. Corpus build | `src/build_corpus.py` | Merges reviewer seed knowledge + agent reports + MCP evidence into `data/verified.csv`. |
| 6. Overrides ledger | `src/make_overrides.py` | Labels every draft→verified correction (agent-report / agent-deep-dive / human-review). |
| 7. Pass 2 | `src/apply.py` | Draft + promoted overrides = verified dataset. |
| 8. Verify | `src/verify.py 2` | Same live checks against pass 2. |
| 9. Composio check | `src/composio_check.py` | Optional: cross-references which apps already have Composio toolkits (degrades gracefully; our key predates the v3 API). |
| 10. Patterns | `src/patterns.py` | Distributions, gating × category crosstabs, blocker clusters, easy-win shortlist — all computed, none hand-written. |
| 11–12. Audit | `src/audit.py 1\|2` | Strict ground-truth scoring of both passes on a hand-verified 20-app sample (`data/audit_sample.csv`). |
| 13. Page | `src/render.py` | Generates `index.html` (single file, inline SVG charts, interactive matrix). |
| 14. Report | `src/report.py` | `out/research_report.json` — machine-readable mirror of the page. |

Agent-produced evidence lives in `out/agent_reports/*.json`: five app-research
groups that fetched official docs live, `mcp_officials.json` (vendor-evidence
MCP classification), and `mcp_sweep_raw.json` (registry sweep).

**Where the human was needed** (also stated on the page): conflict
resolution between sources, the apps with no usable public docs, final
verdict judgment, and promoting corrections. The pipeline never edits
`overrides.csv` by itself.

## Repo layout

```
data/   apps.csv (roster) · verified.csv (final corpus) · research_drafts.csv
        (agent proposals) · overrides.csv (labeled correction ledger) ·
        audit_sample.csv (independent ground truth, 20 apps with sources)
src/    the 14 stages above + config.py, llm.py (cached Gemini client),
        io_utils.py, render_charts.py, render_css.py, report.py
out/    every intermediate artifact — draft, both verification passes,
        audits, patterns, MCP sweep, agent reports, llm_cache, report JSON
index.html  the deliverable (single file, zero external deps, works offline)
```

## Honesty notes

- Audit covers 20 apps field-by-field; the other 80 rows are verified by
  evidence-liveness checks + rules, not human field review. Disclosed on the page.
- The human reviewer and the auditor used the same primary sources; the audit
  exists to grade the untouched first pass and confirm the loop's corrections,
  not to claim independent discovery. The number to trust is the delta.
- MCP status is a snapshot (September 2026); vendors ship servers monthly.
- LLM drafting is nondeterministic — the exact draft used for the published
  numbers is committed in `out/draft_pass1.csv`.
- The provided `COMPOSIO_API_KEY` is rejected by the current v3 API (HTTP 401);
  that stage reports the real error instead of pretending.
