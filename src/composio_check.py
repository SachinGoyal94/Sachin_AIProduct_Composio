"""Cross-check: which of the 100 apps already ship as Composio toolkits?

Auth history, documented honestly:
  - x-api-key against /api/v3/toolkits -> HTTP 401 (key predates v3 / wrong scheme)
  - x-consumer-api-key over MCP (https://connect.composio.dev/mcp) -> works

Final method: MCP streamable-HTTP. We handshake, then call
COMPOSIO_SEARCH_TOOLS once per app ("use_case" = app name) and record which
Composio toolkit matches and how many tools the catalog exposes. Results are
cached per app id under out/composio_mcp_cache/ so re-runs are cheap.

    python src/composio_check.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time

import requests
from dotenv import dotenv_values

from config import COMPOSIO_JSON, ROOT, HTTP_CONCURRENCY
from io_utils import load_apps, write_json

MCP_URL = "https://connect.composio.dev/mcp"
CACHE = ROOT / "out" / "composio_mcp_cache"


def _session() -> tuple[dict, str]:
    ck = dotenv_values(ROOT / ".env").get("COMPOSIO_API_KEY", "")
    if not ck:
        raise RuntimeError("COMPOSIO_API_KEY not set")
    base = {"x-consumer-api-key": ck, "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"}
    r = requests.post(MCP_URL, headers=base, json={
        "jsonrpc": "2.0", "id": 0, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "app-research-100", "version": "1.0"}}},
        timeout=40)
    r.raise_for_status()
    sid = r.headers.get("mcp-session-id")
    if not sid:
        raise RuntimeError(f"MCP handshake returned no session id: {r.text[:120]}")
    requests.post(MCP_URL, headers={**base, "Mcp-Session-Id": sid}, json={
        "jsonrpc": "2.0", "method": "notifications/initialized"}, timeout=30)
    return base, sid


def _rpc(base, sid, payload) -> dict | None:
    """POST a JSON-RPC call; the reply may arrive as several SSE 'data:'
    events (streamed JSON-RPC responses), so collect all of them and return
    the last complete result/error for our request id."""
    h = {**base, "Mcp-Session-Id": sid}
    r = requests.post(MCP_URL, headers=h, json=payload, timeout=90)
    txt = r.text.strip()
    if not txt:
        return None
    rid = payload.get("id")
    events: list = []
    if "data: " in txt:
        for line in txt.splitlines():
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:].strip()))
                except json.JSONDecodeError:
                    continue
    else:
        try:
            events.append(json.loads(txt))
        except json.JSONDecodeError:
            return None
    answers = [e for e in events if isinstance(e, dict) and
               ("result" in e or "error" in e) and
               (rid is None or e.get("id") == rid)]
    return answers[-1] if answers else None


def _load_first_json(text: str) -> dict | None:
    """The tool's text content is a JSON document, but may carry trailing
    bytes; parse the first complete JSON object from it."""
    try:
        obj, _ = json.JSONDecoder().raw_decode(text.strip())
        return obj if isinstance(obj, dict) else None
    except ValueError:
        return None


def _token(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().split()[0])


def search_app(app, base, sid) -> dict:
    """One COMPOSIO_SEARCH_TOOLS call for one app; returns a coverage record."""
    call = _rpc(base, sid, {"jsonrpc": "2.0", "id": 99, "method": "tools/call",
                            "params": {"name": "COMPOSIO_SEARCH_TOOLS",
                                       "arguments": {"queries": [
                                           {"use_case": app.name}]}}})
    content = ((call or {}).get("result", {}).get("content") or [])
    data: dict = {}
    for c in content:
        parsed = _load_first_json(c.get("text", ""))
        if parsed and "data" in parsed:
            data = parsed["data"]
            break
    results = data.get("results", [])
    toolkits = sorted({t for r_ in results for t in r_.get("toolkits", [])})
    tool_slugs = sorted({s for r_ in results for s in r_.get("primary_tool_slugs", [])
                         + r_.get("related_tool_slugs", [])})
    token = _token(app.name)
    covered = any(token and token in t.replace("_", "") for t in toolkits)
    return {"id": app.id, "app": app.name, "covered": covered,
            "toolkits": toolkits, "n_tools": len(tool_slugs),
            "tool_slugs": tool_slugs[:12]}


def main() -> None:
    apps = load_apps()
    result: dict = {"generated": dt.datetime.now().isoformat(timespec="seconds"),
                    "ok": False, "method": "", "error": "", "note": "",
                    "apps": []}
    try:
        base, sid = _session()
        tools = _rpc(base, sid, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        n_tools = len((tools or {}).get("result", {}).get("tools", []))
        result["mcp_tools"] = n_tools
        CACHE.mkdir(parents=True, exist_ok=True)
        records = []
        for app in apps:
            cache_file = CACHE / f"{app.id}.json"
            if cache_file.exists():
                rec = json.loads(cache_file.read_text(encoding="utf-8"))
            else:
                try:
                    rec = search_app(app, base, sid)
                except Exception as e:  # noqa: BLE001 - record and continue
                    rec = {"id": app.id, "app": app.name, "covered": False,
                           "toolkits": [], "n_tools": 0, "tool_slugs": [],
                           "error": f"{type(e).__name__}: {e}"[:160]}
                    time.sleep(1.0)
                cache_file.write_text(json.dumps(rec, ensure_ascii=False),
                                      encoding="utf-8")
            records.append(rec)
        covered = [r_ for r_ in records if r_["covered"] and not r_.get("error")]
        result.update({
            "ok": True,
            "method": f"Composio MCP (connect.composio.dev/mcp) - "
                      f"COMPOSIO_SEARCH_TOOLS x{len(records)}",
            "apps": records,
            "covered_ids": sorted(r_["id"] for r_ in covered),
            "n_covered": len(covered),
            "note": f"{len(covered)}/{len(apps)} of the researched apps already "
                    f"ship as Composio toolkits (live MCP catalog search)",
        })
    except Exception as e:  # noqa: BLE001 - stage is optional; report the truth
        result["error"] = f"{type(e).__name__}: {e}"[:300]
        result["note"] = ("Composio cross-check failed; stage is optional and "
                          "reports the real error rather than guessing.")
    write_json(COMPOSIO_JSON, result)
    print(f"composio_check: ok={result['ok']} "
          f"{result.get('note') or result['error']}")


if __name__ == "__main__":
    main()
