"""Live HTTP checks: fetch evidence URLs and verify claims against the real web.

The verification loop works in three directions:
  1. evidence_check - does the cited evidence URL exist and mention the claimed auth?
  2. mcp_check      - do MCP 'Yes' claims hold up against public registries?
  3. docs_probe     - probe well-known docs/API paths for liveness (independent signal)

Runs concurrently (ThreadPoolExecutor). Metrics are honest by construction:
MCP confirmation is computed ONLY over apps that claim MCP = 'Yes' ('No' claims
are not evidence of anything and are excluded, not auto-passed).

Usage:  python verify.py [pass_no]
"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from config import AppRecord, http_get

MAX_WORKERS = 12
N_REQUESTS = 0  # total live HTTP requests made by this stage (reported in summary)


def _get(url: str, timeout: float = 6.0) -> tuple[int, str]:
    global N_REQUESTS
    N_REQUESTS += 1
    return http_get(url, timeout=timeout)


# Terms that count as textual confirmation of each auth claim when found in
# the fetched evidence page. Deliberately specific: a bare "access token" or
# "signature" match is too loose (OAuth2 pages mention access tokens; webhook
# docs mention signatures) and would inflate the confirmation rate.
AUTH_TERM_MAP = {
    "OAuth2": [r"oauth\s*2", r"oauth2", r"oauth 2\.0"],
    "OAuth1": [r"oauth\s*1", r"oauth1", r"oauth 1\.0a"],
    "API key": [r"api[_ -]?key", r"x-api-key", r"x-api-token", r"apikey"],
    "Bearer token": [
        r"bearer",
        r"personal access token",
        r"api token",
        r"integration token",
    ],
    "Basic": [r"basic auth", r"http basic", r"basic\s+auth", r"account sid"],
    "JWT": [r"\bjwt\b", r"json web token"],
    "HMAC": [r"\bhmac\b", r"signed request"],
    "None": [r"no authentication", r"without authentication", r"no auth"],
}

# Registries queried for MCP confirmation. The official MCP registry is the
# canonical source; Smithery's registry is a large second source.
MCP_SEARCH_ENDPOINTS = [
    ("official-registry", "https://registry.modelcontextprotocol.io/v0/servers?search={q}"),
    ("smithery-registry", "https://registry.smithery.ai/servers?q={q}"),
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def _strip_html(body: str) -> str:
    return _norm(re.sub(r"<[^>]+>", " ", body))


def evidence_check(rec: AppRecord) -> dict:
    """Fetch the cited evidence URL; confirm it is alive and mentions the claim."""
    status, body = _get(rec.evidence, timeout=8)
    text = _strip_html(body)
    hits: list[str] = []
    for term in AUTH_TERM_MAP.get(rec.auth, []):
        if re.search(term, text):
            hits.append(term)
    auth_confirmed = bool(hits)
    if rec.auth == "None":
        # for 'None' auth, alive page is the checkable part
        auth_confirmed = status == 200
    return {
        "kind": "evidence",
        "url": rec.evidence,
        "status": status,
        "auth_terms_found": hits[:3],
        "auth_confirmed": auth_confirmed,
        "alive": status == 200,
        "ok": status == 200 and auth_confirmed,
    }


def _mcp_listing_matches(body: str, query: str) -> bool:
    b = _norm(body)
    tokens = [t for t in re.split(r"\s+", query.lower()) if len(t) > 2]
    if not tokens:
        return False
    if query.lower() in b and ("server" in b or "mcp" in b):
        return True
    if all(t in b for t in tokens) and "server" in b:
        return True
    return False


def mcp_check(rec: AppRecord) -> dict:
    """Confirm an MCP 'Yes' claim by querying public registries.

    'No' claims are skipped (nothing to confirm); the summary therefore
    reports confirmation over Yes-claiming apps only.
    """
    if rec.mcp != "Yes":
        return {"kind": "mcp", "ok": None, "skipped": f"MCP claimed {rec.mcp!r}; nothing to confirm"}
    queries = [rec.name]
    special = {
        "Mermaid CLI": ["mermaid"],
        "YouTube Transcript": ["youtube transcript", "youtube"],
        "WhatsApp Business": ["whatsapp"],
        "Salesforce": ["salesforce"],
        "Threads": ["threads"],
        "Meta Ads": ["meta ads", "facebook ads"],
        "Google Ads": ["google ads"],
        "LinkedIn Ads": ["linkedin"],
        "Monday.com": ["monday"],
        "NotebookLM": ["notebooklm"],
    }
    if rec.name in special:
        queries = special[rec.name]

    for provider, tpl in MCP_SEARCH_ENDPOINTS:
        for q in queries:
            url = tpl.format(q=q.replace(" ", "%20"))
            status, body = _get(url, timeout=10)
            if status != 200:
                continue
            if _mcp_listing_matches(body, q):
                return {"kind": "mcp", "ok": True, "provider": provider, "query": q, "url": url}
    # registry miss: the claim is UNCONFIRMED, not false - registry coverage is
    # heuristic (name matching), so this is reported as its own outcome.
    return {"kind": "mcp", "ok": False, "unconfirmed": True, "claimed": rec.mcp}


def docs_probe(rec: AppRecord) -> dict:
    """Independent liveness probe: docs URL, site root, and /openapi.json."""
    base = urlparse(rec.evidence)
    root = f"{base.scheme}://{base.netloc}"
    probes = [rec.evidence, root, root + "/openapi.json"]
    results = []
    for url in probes:
        status, _ = _get(url, timeout=6)
        results.append({"url": url, "status": status})
    live = any(r["status"] == 200 for r in results)
    return {"kind": "docs_probe", "ok": live, "probes": results}


def _check_app(rec: AppRecord) -> dict:
    ev = evidence_check(rec)
    mc = mcp_check(rec)
    dp = docs_probe(rec)
    return {"id": rec.id, "name": rec.name, "evidence": ev, "mcp": mc, "docs_probe": dp}


def run_verification(records: list[AppRecord], verbose: bool = True) -> dict:
    """Run the full verification loop over all records concurrently."""
    global N_REQUESTS
    N_REQUESTS = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        results = list(ex.map(_check_app, records))

    total = len(results)
    n_ev = sum(1 for r in results if r["evidence"]["ok"])
    n_alive = sum(1 for r in results if r["evidence"]["alive"])
    yes_rows = [r for r in results if r["mcp"]["ok"] is not None]
    yes_conf = sum(1 for r in yes_rows if r["mcp"]["ok"])
    n_probe = sum(1 for r in results if r["docs_probe"]["ok"])
    report = {
        "results": results,
        "summary": {
            "total": total,
            "n_http_requests": N_REQUESTS,
            "evidence_ok": n_ev,
            "evidence_pct": round(100 * n_ev / total, 1),
            "evidence_alive": n_alive,
            "evidence_alive_pct": round(100 * n_alive / total, 1),
            "mcp_yes_total": len(yes_rows),
            "mcp_yes_confirmed": yes_conf,
            "mcp_yes_pct": round(100 * yes_conf / len(yes_rows), 1) if yes_rows else 0.0,
            "docs_probe_ok": n_probe,
            "docs_probe_pct": round(100 * n_probe / total, 1),
        },
    }
    if verbose:
        s = report["summary"]
        print(f"  HTTP requests made:            {s['n_http_requests']}")
        print(f"  evidence URL alive:            {s['evidence_alive']}/{total} ({s['evidence_alive_pct']}%)")
        print(f"  evidence alive+auth-confirmed: {s['evidence_ok']}/{total} ({s['evidence_pct']}%)")
        print(f"  MCP 'Yes' claims confirmed:    {s['mcp_yes_confirmed']}/{s['mcp_yes_total']} ({s['mcp_yes_pct']}%)")
        print(f"  docs probe reachable:          {s['docs_probe_ok']}/{total} ({s['docs_probe_pct']}%)")
        fails = [r for r in results
                 if not (r["evidence"]["ok"] and (r["mcp"]["ok"] is None or r["mcp"]["ok"]))]
        print(f"  apps needing attention: {len(fails)}")
        for r in fails[:30]:
            print(f"    - #{r['id']:3d} {r['name']}: ev={r['evidence']['status']} "
                  f"auth_ok={r['evidence']['auth_confirmed']} mcp_ok={r['mcp']['ok']}")
    return report


if __name__ == "__main__":
    from io_utils import apply_overrides, load_records, save_json

    pass_no = sys.argv[1] if len(sys.argv) > 1 else "1"
    recs = load_records()
    if int(pass_no) >= 2:
        recs, _ = apply_overrides(recs)
    rep = run_verification(recs)
    save_json(rep, f"verification_pass{pass_no}.json")
    print(json.dumps(rep["summary"], indent=2))
