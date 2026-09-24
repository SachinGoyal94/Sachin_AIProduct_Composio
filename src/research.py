"""Agentic research stage: search -> fetch -> extract -> DRAFT corrections.

This is the stage that makes the pipeline a research agent rather than a
fact-checker. For every app the knowledge core flags low-confidence, the
agent runs a live, keyless research loop:

  1. SEARCH  - keyless web search (Bing HTML) for the app's API auth docs
  2. FETCH   - pull the top candidate pages, preferring official domains
  3. EXTRACT - deterministic detectors read auth / MCP / gating signals
               out of the page text, with source snippets
  4. DRAFT   - extracted corrections are written to data/research_drafts.csv

Drafts are NEVER auto-applied. A human reviews the draft file and promotes
accepted rows into data/overrides.csv - the single correction path the
pipeline trusts. Rejected drafts stay in the file with status=rejected so
the page can show where the agent over-reached.

The loop intentionally has no LLM and no API keys: every extraction is a
regex over a fetched page attached to a URL, so a reviewer can re-verify any
draft by opening its source_url. Verdict/breadth are deliberately NOT drafted
- they require judgment the extractors don't have; that stays human.

Usage:
    python research.py            # research the pass-1 low-confidence set
    python research.py --all      # research all 100 apps
"""
from __future__ import annotations

import base64
import csv
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

from config import DATA, OUT, AppRecord, http_get
from io_utils import apply_overrides, load_records, save_json
from verify import AUTH_TERM_MAP

N_REQUESTS = 0
SEARCH_URL = "https://www.bing.com/search?q={q}&count=10"
FETCH_WORKERS = 6
SEARCH_GAP_S = 0.7
MAX_CANDIDATES = 4

SKIP_URL_PARTS = ("bing.com", "microsoft.com/en-us/bing", "msn.com", "youtube.com/watch",
                  "facebook.com/login", "twitter.com", "x.com/", "linkedin.com/login")

# App-name tokens too generic to identify an official domain.
NAME_STOPWORDS = {"ai", "cli", "api", "ads", "app", "the", "cloud", "connect", "business"}

# ---- extractors -------------------------------------------------------------
MCP_PATTERNS = [r"model context protocol", r"\bmcp\s+(server|client|integration)s?\b",
                r"mcp\."]

SELF_SERVE_PATTERNS = [
    r"generate (an )?api key", r"create (an )?api key", r"api key (is|can be) (generated|created)",
    r"api keys? (in|from|via) (your |the )?(dashboard|settings|account|admin)",
    r"sign ?up .{0,40}(free|trial|instantly)", r"get started .{0,30}free",
    r"available (on|to) (all|every) plans", r"self-serve",
]
GATED_PATTERNS = [
    r"contact (sales|our sales|us)", r"app review", r"approval process",
    r"(requires?|needs?) (approval|verification|vetting)", r"waitlist",
    r"request access", r"enterprise plan required", r"sales-led",
]


@dataclass
class Signals:
    auth_hits: dict = field(default_factory=dict)   # auth -> [(term, snippet)]
    mcp_snippets: list = field(default_factory=list)
    self_serve_snippets: list = field(default_factory=list)
    gated_snippets: list = field(default_factory=list)
    url: str = ""


def _get(url: str, timeout: float = 10.0) -> tuple[int, str]:
    global N_REQUESTS
    N_REQUESTS += 1
    return http_get(url, timeout=timeout)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def strip_html(body: str) -> str:
    return _norm(re.sub(r"<[^>]+>", " ", body))


def _snippets(text: str, pattern: str, limit: int = 2) -> list[tuple[str, str]]:
    """Return up to `limit` (matched_term, context_snippet) pairs for a regex."""
    out = []
    for m in re.finditer(pattern, text, re.IGNORECASE):
        i = m.start()
        out.append((m.group(0)[:40], text[max(0, i - 70):i + 90].strip()))
        if len(out) >= limit:
            break
    return out


# ---- search -----------------------------------------------------------------
def _decode_bing_url(href: str) -> str | None:
    """Extract the real target from a Bing /ck/a redirect URL."""
    m = re.search(r"[?&]u=a1([A-Za-z0-9+/=_-]+)", href)
    if not m:
        return href if href.startswith("http") else None
    b64 = m.group(1).replace("_", "/").replace("-", "+")
    b64 += "=" * (-len(b64) % 4)
    try:
        return base64.b64decode(b64).decode("utf-8", errors="ignore")
    except Exception:
        return None


def bing_search(query: str) -> list[str]:
    """Keyless web search. Returns decoded result URLs (may be empty if blocked)."""
    status, body = _get(SEARCH_URL.format(q=query.replace(" ", "+")), timeout=12)
    if status != 200:
        return []
    urls = []
    for m in re.finditer(r'<li class="b_algo".*?<h2[^>]*><a[^>]*href="([^"]+)"', body, re.S):
        url = _decode_bing_url(m.group(1))
        if url:
            urls.append(url)
    return urls


def candidates_for(rec: AppRecord, search_ok: bool) -> list[str]:
    """Build candidate doc URLs: search results + deterministic docs-path probes."""
    host = urlparse(rec.evidence).netloc
    seen, out = set(), []

    def add(urls: list[str]) -> None:
        for u in urls:
            if not u or not u.startswith("http"):
                continue
            low = u.lower()
            if any(s in low for s in SKIP_URL_PARTS):
                continue
            if urlparse(u).netloc not in seen:
                seen.add(urlparse(u).netloc)
                out.append(u)

    if search_ok:
        for q in (f"{rec.name} API authentication documentation",
                  f"{rec.name} developer API docs"):
            add(bing_search(q))
            time.sleep(SEARCH_GAP_S)
    # deterministic probes always run: cited evidence first, then docs-path guesses
    add([rec.evidence, f"https://{host}", f"https://{host}/docs", f"https://{host}/developers"])
    bare = host.removeprefix("www.").removeprefix("developers.").removeprefix("developer.")
    bare = ".".join(bare.split(".")[-2:])
    if not host.startswith(("developers.", "developer.", "docs.", "api.")):
        add([f"https://developers.{bare}", f"https://docs.{bare}"])
    return out[:MAX_CANDIDATES + 3]


# ---- extraction -------------------------------------------------------------
def name_tokens(rec: AppRecord) -> list[str]:
    toks = {t.lower() for t in re.split(r"[\s.\-]+", rec.name)} - NAME_STOPWORDS
    return [t for t in toks if len(t) > 2]


def is_official(url: str, rec: AppRecord) -> bool:
    netloc = urlparse(url).netloc.lower()
    toks = name_tokens(rec)
    if any(t in netloc for t in toks):
        return True
    hint_netloc = urlparse(rec.evidence).netloc.lower()
    return netloc == hint_netloc or netloc.endswith("." + hint_netloc) or hint_netloc.endswith("." + netloc)


def extract(url: str, body: str) -> Signals:
    """Run every detector over one fetched page."""
    text = strip_html(body).lower()
    sig = Signals(url=url)
    for auth, pats in AUTH_TERM_MAP.items():
        hits = []
        for p in pats:
            hits += _snippets(text, p)
        if hits:
            sig.auth_hits[auth] = hits
    for p in MCP_PATTERNS:
        sig.mcp_snippets += _snippets(text, p, limit=1)
    for p in SELF_SERVE_PATTERNS:
        sig.self_serve_snippets += _snippets(text, p, limit=1)
    for p in GATED_PATTERNS:
        sig.gated_snippets += _snippets(text, p, limit=1)
    return sig


def _auth_draft(auth_hits: dict) -> tuple[str | None, str]:
    """Pick a single dominant auth family, or None if ambiguous/absent."""
    strong = {a: h for a, h in auth_hits.items() if a != "None"}
    if not strong:
        return None, ""
    if len(strong) == 1:
        a = next(iter(strong))
        return a, f"page text mentions {a} auth"
    ranked = sorted(strong, key=lambda a: -len(strong[a]))
    if len(ranked) >= 2 and len(strong[ranked[0]]) > len(strong[ranked[1]]):
        return ranked[0], f"dominant auth signal ({len(strong[ranked[0]])} hits) = {ranked[0]}"
    return None, "ambiguous: " + ", ".join(f"{a}({len(h)})" for a, h in strong.items())


# ---- per-app loop -----------------------------------------------------------
@dataclass
class AppResearch:
    id: int
    name: str
    queries: int = 0
    search_results: int = 0
    pages_fetched: int = 0
    official_pages: int = 0
    signals: list = field(default_factory=list)
    drafts: list = field(default_factory=list)
    note: str = ""


def research_app(rec: AppRecord, prior: dict) -> AppResearch:
    ar = AppResearch(id=rec.id, name=rec.name)
    probe_results = candidates_for(rec, search_ok=True)
    ar.search_results = len(probe_results)
    ar.queries = 2

    bodies: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
        fetched = dict(zip(probe_results, ex.map(
            lambda u: _get(u, timeout=10)[1], probe_results)))
    for url, body in fetched.items():
        if not body.startswith("__ERROR__") and len(body) > 500:
            ar.pages_fetched += 1
            bodies[url] = body

    sigs = []
    for url, body in bodies.items():
        sig = extract(url, body)
        if is_official(url, rec):
            ar.official_pages += 1
            sigs.append(sig)
    ar.signals = [{"url": s.url, "auth": {a: h[:1] for a, h in s.auth_hits.items()},
                   "mcp": bool(s.mcp_snippets),
                   "self_serve": bool(s.self_serve_snippets),
                   "gated": bool(s.gated_snippets)} for s in sigs]
    if not sigs:
        ar.note = "no fetchable doc pages (blocked/SPA/no results) - left for human"
        return ar
    official = sigs if ar.official_pages else []

    def draft(field: str, value: str, note: str, source: Signals):
        if prior.get(field) == value:
            return  # agrees with pass-1 prior; nothing to correct
        ar.drafts.append({"id": rec.id, "name": rec.name, "field": field,
                          "value": value, "note": f"agent draft: {note}",
                          "source_url": source.url, "status": "draft"})

    if official:
        auth_val, why = _auth_draft({a: h for s in official for a, h in s.auth_hits.items()})
        if auth_val:
            src = next(s for s in official if auth_val in s.auth_hits)
            draft("auth", auth_val, why, src)
        if any(s.mcp_snippets for s in official) and prior.get("mcp") != "Yes":
            src = next(s for s in official if s.mcp_snippets)
            draft("mcp", "Yes", "official page documents an MCP server", src)
        ss = [s for s in official if s.self_serve_snippets]
        gt = [s for s in official if s.gated_snippets]
        if ss and not gt and prior.get("gate") == "Gated":
            draft("gate", "Self-serve", "official page shows self-serve key generation", ss[0])
        elif gt and not ss and str(prior.get("gate", "")).startswith("Self-serve"):
            draft("gate", "Gated", "official page shows approval/contact-sales language", gt[0])
        best = official[0]
        if urlparse(best.url).netloc != urlparse(prior.get("evidence", "")).netloc:
            draft("evidence", best.url, "stronger official source found by search", best)
    else:
        ar.note = "signals found only on non-official pages - drafts suppressed"
    return ar


def run(research_all: bool = False) -> dict:
    global N_REQUESTS
    N_REQUESTS = 0
    pristine = load_records()  # pass-1 priors are the drafting baseline
    pass1 = {r.id: r for r in pristine}
    final, _ = apply_overrides(load_records())  # current human-verified values
    final_by_id = {r.id: r for r in final}
    targets = pristine if research_all else [r for r in pristine if r.confidence < 3]
    print(f"researching {len(targets)} apps "
          f"({'all' if research_all else 'pass-1 low-confidence set'}), keyless loop...")

    apps = []
    for rec in targets:
        ar = research_app(rec, prior={**pass1[rec.id].__dict__})
        apps.append(ar)
        if ar.drafts:
            print(f"  #{rec.id:3d} {rec.name}: {len(ar.drafts)} draft(s) "
                  f"({', '.join(d['field'] + '=' + d['value'][:24] for d in ar.drafts)})")

    # agent-vs-human agreement: each draft vs the current human-verified value
    for ar in apps:
        fin = final_by_id[ar.id]
        for d in ar.drafts:
            cur = str(getattr(fin, d["field"]))
            d["agrees_with_final"] = (cur == d["value"])
            d["final_value"] = cur

    drafts = [d for ar in apps for d in ar.drafts]
    out_csv = DATA / "research_drafts.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "field", "value", "note",
                                          "source_url", "status", "agrees_with_final",
                                          "final_value"])
        w.writeheader()
        w.writerows(drafts)

    n_agree = sum(1 for d in drafts if d["agrees_with_final"])
    report = {
        "summary": {
            "n_apps_targeted": len(targets),
            "n_apps_researched": sum(1 for a in apps if a.pages_fetched),
            "n_http_requests": N_REQUESTS,
            "n_drafts": len(drafts),
            "n_drafts_agree_with_final": n_agree,
            "n_drafts_disagree": len(drafts) - n_agree,
            "n_apps_with_drafts": sum(1 for a in apps if a.drafts),
            "note": "drafts are proposals - never auto-applied; human promotes to overrides.csv",
        },
        "apps": [a.__dict__ for a in apps],
    }
    save_json(report, "research_report.json")
    s = report["summary"]
    print(f"research loop: {s['n_http_requests']} HTTP requests, "
          f"{s['n_drafts']} drafts on {s['n_apps_with_drafts']} apps "
          f"({s['n_drafts_agree_with_final']} agree with human-verified final values)")
    return report


if __name__ == "__main__":
    run(research_all="--all" in __import__("sys").argv)
