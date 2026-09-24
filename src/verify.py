"""Live HTTP checks: fetch evidence URLs and verify claims against the real web.

The verification loop works in three directions:
  1. evidence_check - does the cited evidence URL exist and mention the claimed auth?
  2. mcp_check      - does the cited MCP claim hold up against public registries?
  3. docs_probe     - probe well-known docs/API paths for liveness (independent signal)

Runs concurrently (ThreadPoolExecutor) - 100 apps x ~6 requests in well under a minute.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from config import AppRecord, http_get

MAX_WORKERS = 12

# Terms that count as textual confirmation of each auth claim when found in
# the fetched evidence page.
AUTH_TERM_MAP = {
    "OAuth2": [r"oauth\s*2", r"oauth2", r"oauth 2\.0"],
    "OAuth1": [r"oauth\s*1", r"oauth1", r"oauth 1\.0a"],
    "API key": [r"api[_ -]?key", r"x-api-key", r"apikey"],
    "Bearer token": [
        r"bearer",
        r"personal access token",
        r"access token",
        r"session token",
        r"api token",
        r"integration token",
    ],
    "Basic": [r"basic auth", r"http basic", r"basic\s+auth", r"account sid"],
    "JWT": [r"\bjwt\b", r"json web token"],
    "HMAC": [r"\bhmac\b", r"signature", r"signed request"],
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
    status, body = http_get(rec.evidence, timeout=8)
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


def _mcp_listing_matches(body: str, name: str, query: str) -> bool:
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
    """Confirm the MCP claim by querying public registries (PulseMCP, Smithery)."""
    if rec.mcp == "No":
        return {"kind": "mcp", "ok": True, "skipped": "no MCP claimed"}
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
            status, body = http_get(url, timeout=10)
            if status != 200:
                continue
            if _mcp_listing_matches(body, rec.name, q):
                return {"kind": "mcp", "ok": True, "provider": provider, "query": q, "url": url}
    return {"kind": "mcp", "ok": False, "claimed": rec.mcp}


def docs_probe(rec: AppRecord) -> dict:
    """Independent liveness probe: docs URL, site root, and /openapi.json."""
    base = urlparse(rec.evidence)
    root = f"{base.scheme}://{base.netloc}"
    probes = [rec.evidence, root, root + "/openapi.json"]
    results = []
    for url in probes:
        status, _ = http_get(url, timeout=6)
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
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        results = list(ex.map(_check_app, records))

    n_ev = sum(1 for r in results if r["evidence"]["ok"])
    n_alive = sum(1 for r in results if r["evidence"]["alive"])
    n_mcp = sum(1 for r in results if r["mcp"]["ok"])
    n_probe = sum(1 for r in results if r["docs_probe"]["ok"])
    total = len(results)
    report = {
        "results": results,
        "summary": {
            "total": total,
            "evidence_ok": n_ev,
            "evidence_pct": round(100 * n_ev / total, 1),
            "evidence_alive": n_alive,
            "evidence_alive_pct": round(100 * n_alive / total, 1),
            "mcp_ok": n_mcp,
            "mcp_pct": round(100 * n_mcp / total, 1),
            "docs_probe_ok": n_probe,
            "docs_probe_pct": round(100 * n_probe / total, 1),
        },
    }
    if verbose:
        s = report["summary"]
        print(f"  evidence URL alive:            {s['evidence_alive']}/{total} ({s['evidence_alive_pct']}%)")
        print(f"  evidence alive+auth-confirmed: {s['evidence_ok']}/{total} ({s['evidence_pct']}%)")
        print(f"  MCP claims consistent:         {s['mcp_ok']}/{total} ({s['mcp_pct']}%)")
        print(f"  docs probe reachable:          {s['docs_probe_ok']}/{total} ({s['docs_probe_pct']}%)")
        fails = [r for r in results if not (r["evidence"]["ok"] and r["mcp"]["ok"])]
        print(f"  apps needing attention: {len(fails)}")
        for r in fails[:30]:
            print(f"    - #{r['id']:3d} {r['name']}: ev={r['evidence']['status']} "
                  f"auth_ok={r['evidence']['auth_confirmed']} mcp_ok={r['mcp']['ok']}")
    return report


if __name__ == "__main__":
    import sys

    from io_utils import apply_overrides, load_records, save_json

    pass_no = sys.argv[1] if len(sys.argv) > 1 else "1"
    recs = load_records()
    if int(pass_no) >= 2:
        recs, _ = apply_overrides(recs)
    rep = run_verification(recs)
    save_json(rep, f"verification_pass{pass_no}.json")
    print(json.dumps(rep["summary"], indent=2))
