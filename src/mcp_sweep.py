"""MCP sweep: query the official MCP registry for every app.

Mechanical evidence collection only - the script records every registry
hit (server name, repo URL) per app. Classification into official vs
community happens in build_corpus.py, where the reviewer maps vendor-owned
repos; anything with a registry hit but no vendor repo is "Yes (community)",
and apps with no hit at all are "No".

    python src/mcp_sweep.py
"""
from __future__ import annotations

import concurrent.futures as cf

import requests

from config import OUT, HTTP_CONCURRENCY
from io_utils import load_apps, write_json

REGISTRY = "https://registry.modelcontextprotocol.io/v0/servers"

# search terms per app id (empty -> use name); tuned to registry naming
SEARCH = {
    44: "salesforce commerce", 45: "magento", 49: "amazon selling partner",
    51: "dataforseo", 57: "bright data", 58: "sherlock",
    59: "waterfall", 68: "mongodb", 74: "jira", 76: "monday",
    83: "binance", 84: "paygent", 85: "ipayx", 91: "notebooklm",
    92: "otter", 96: "devin", 97: "higgsfield", 98: "mermaid",
    99: "youtube transcript", 24: "lark", 28: "whatsapp",
    32: "meta ads", 33: "linkedin", 34: "gohighlevel",
}


def sweep_app(app) -> dict:
    term = SEARCH.get(app.id, app.name.lower())
    for clean in (app.name, term) if term != app.name.lower() else (term,):
        q = clean.lower().replace(" (", " ").replace(")", " ").strip()
        q = " ".join(q.split()[:3])
        try:
            r = requests.get(REGISTRY, params={"search": q, "limit": 8}, timeout=20)
            if r.status_code != 200:
                continue
            servers = r.json().get("servers", [])
            if servers:
                hits = []
                for s in servers[:6]:
                    srv = s.get("server", {})
                    hits.append({
                        "name": srv.get("name", ""),
                        "repo": (srv.get("repository") or {}).get("url", ""),
                        "desc": (srv.get("description") or "")[:120],
                    })
                return {"id": app.id, "hits": hits}
        except requests.RequestException:
            continue
    return {"id": app.id, "hits": []}


def main() -> None:
    apps = load_apps()
    with cf.ThreadPoolExecutor(HTTP_CONCURRENCY) as ex:
        results = sorted(ex.map(sweep_app, apps), key=lambda r: r["id"])
    n_hits = sum(1 for r in results if r["hits"])
    write_json(OUT / "mcp_sweep_raw.json", {"generated_by": "registry.modelcontextprotocol.io",
                                            "results": results})
    print(f"mcp sweep: {n_hits}/{len(apps)} apps have registry hits "
          f"-> out/mcp_sweep_raw.json")


if __name__ == "__main__":
    main()
