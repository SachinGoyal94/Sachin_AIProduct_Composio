# app-research/100 — agent-researched API integration landscape

One agent + one verification loop researched **100 SaaS apps across 10
categories**: auth methods, self-serve vs gated credential access, API
surface, MCP (Model Context Protocol) coverage, and a buildability verdict —
with an evidence URL behind every row and an audited accuracy trail.

Built as a take-home case study for Composio's AI Product Ops role.
**Open `index.html`** — the whole case study is one self-explanatory page.

## How to run the research agent

```bash
git clone <this repo> && cd <repo>
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # add GEMINI_API_KEY (Google AI Studio key)
python src/run_all.py       # full run: ~10 stages, a few minutes
```

Offline (rebuild the page from committed artifacts, no network, no key):

```bash
python src/run_all.py --offline
```

## What the pipeline does

| Stage | Script | What happens |
|---|---|---|
| 1. Pass 1 — draft | `src/agent_draft.py` | Gemini 2.5 Flash drafts all 100 apps **from memory only** (batched, cached to `out/llm_cache/`). The honest, unverified first pass. |
| 2. Verify | `src/verify.py 1` | Fetches every evidence URL live (status, redirects, auth-keyword sniffing) + a contradiction rule engine. |
| 3. Deep-dive | `src/research.py` | For flagged rows: fetch real docs pages, LLM extracts facts **strictly from that text** with verbatim quotes → proposals. |
| 4. Human loop | *(you)* | Proposals land in `data/research_drafts.csv`; a human promotes accepted corrections into `data/overrides.csv`. Never auto-applied. |
| 5. Pass 2 | `src/apply.py` | Draft + promoted overrides = verified dataset. |
| 6. Verify | `src/verify.py 2` | Same live checks against pass 2. |
| 7. Composio check | `src/composio_check.py` | Optional: cross-references which apps already have Composio toolkits (degrades gracefully; our key predates the v3 API). |
| 8. Patterns | `src/patterns.py` | Distributions, gating × category crosstabs, blocker clusters, easy-win shortlist — all computed, none hand-written. |
| 9. Audit | `src/audit.py 1\|2` | Strict ground-truth scoring of both passes on a hand-verified 20-app sample (`data/audit_sample.csv`). |
| 10. Render | `src/render.py` + `src/report.py` | Generates `index.html` + `out/research_report.json` from the artifacts. |

**Where the human was needed** (also stated on the page): conflict
resolution between sources, the apps with no usable public docs, final
verdict judgment, and promoting corrections. The pipeline never edits
`overrides.csv` by itself.

## Repo layout

```
data/   apps.csv (roster) · verified.csv (final corpus) · research_drafts.csv
        (agent proposals) · overrides.csv (human-promoted fixes) ·
        audit_sample.csv (independent ground truth)
src/    the ten stages above
out/    every intermediate artifact — draft, both verification passes,
        audits, patterns, MCP registry sweep, agent reports, report JSON
index.html  the deliverable (single file, zero external deps, works offline)
```

## Honesty notes

- Audit covers 20 apps field-by-field; the other 80 rows are verified by
  evidence-liveness checks + rules, not human field review. Disclosed on the page.
- MCP status is a snapshot (September 2026); vendors ship servers monthly.
- LLM drafting is nondeterministic — the exact draft used for the published
  numbers is committed in `out/draft_pass1.csv`.
- The provided `COMPOSIO_API_KEY` is rejected by the current v3 API (HTTP 401);
  that stage reports the real error instead of pretending.
