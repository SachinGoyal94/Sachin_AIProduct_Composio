"""Composio cross-check — over Composio's own MCP gateway.

Connects to https://connect.composio.dev/mcp as a real MCP client:
  initialize -> notifications/initialized -> tools/list -> tools/call
and drives COMPOSIO_SEARCH_TOOLS in batches (one query per researched app).

For every app in our 100 we parse the returned tool names (e.g.
GITHUB_CREATE_ISSUE -> prefix 'github'), count Composio's toolkit size, and
report the overlap. An overlap is an independent, vendor-side confirmation
that the app is agent-callable today through Composio.

Auth: Authorization: Bearer $COMPOSIO_API_KEY (from .env). Optional stage:
without a key the pipeline completes and the page shows the cross-check as
skipped.
"""
from __future__ import annotations

import json
import os
import re
import time

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*a, **k):
        return False

from config import ROOT, AppRecord, env

MCP_URL = "https://connect.composio.dev/mcp"
BATCH = 1          # one use_case per tools/call - batching is flaky server-side
CALL_GAP_S = 1.0   # polite spacing between MCP calls
TOOL_TOKEN = re.compile(r"\b([A-Z][A-Z0-9]{1,20}(?:_[A-Z0-9]+)+)\b")

SLUG_HINTS = {
    # previously-missed apps (were silently skipped from the cross-check)
    "DealCloud": ["dealcloud"],
    "Salesforce Commerce Cloud": ["sfcc", "commercecloud", "salesforcecommerce"],
    "Magento": ["magento", "adobecommerce"],
    "Amazon SP-API": ["sellingpartner", "spapi", "amazonselling"],
    "Fanbasis": ["fanbasis"],
    "Sherlock": ["sherlock"],
    "Paygent Connect": ["paygent", "nmi"],
    "iPayX": ["ipayx"],
    "Mermaid CLI": ["mermaid"],
    "Salesforce": ["salesforce"], "HubSpot": ["hubspot"], "Pipedrive": ["pipedrive"],
    "Attio": ["attio"], "Twenty": ["twenty"], "Zoho CRM": ["zoho"],
    "Close": ["close"], "Copper": ["copper"], "Podio": ["podio"],
    "Zendesk": ["zendesk"], "Intercom": ["intercom"], "Freshdesk": ["freshdesk"],
    "Front": ["front"], "Pylon": ["pylon"], "LiveAgent": ["liveagent"],
    "Plain": ["plain"], "Help Scout": ["helpscout", "help"],
    "Gorgias": ["gorgias"], "Gladly": ["gladly"],
    "Slack": ["slack"], "Twilio": ["twilio"], "Zoho Cliq": ["zoho"],
    "Lark": ["lark"], "Pumble": ["pumble"], "Discord": ["discord"],
    "Telegram": ["telegram"], "WhatsApp Business": ["whatsapp"],
    "Aircall": ["aircall"], "Vonage": ["vonage"],
    "Google Ads": ["googleads", "google"], "Meta Ads": ["metaads", "meta", "facebook"],
    "LinkedIn Ads": ["linkedin"], "GoHighLevel": ["gohighlevel", "highlevel"],
    "Mailchimp": ["mailchimp"], "Klaviyo": ["klaviyo"], "Systeme.io": ["systeme"],
    "Pinterest": ["pinterest"], "Threads": ["threads"], "SendGrid": ["sendgrid"],
    "Shopify": ["shopify"], "WooCommerce": ["woocommerce"],
    "BigCommerce": ["bigcommerce"], "Squarespace": ["squarespace"],
    "Ecwid": ["ecwid"], "Gumroad": ["gumroad"],
    "DataForSEO": ["dataforseo"], "SE Ranking": ["seranking"],
    "Ahrefs": ["ahrefs"], "MrScraper": ["mrscraper"], "Apify": ["apify"],
    "Firecrawl": ["firecrawl"], "Bright Data": ["brightdata", "bright"],
    "Waterfall": ["waterfall"], "Clay": ["clay"],
    "GitHub": ["github"], "Vercel": ["vercel"], "Netlify": ["netlify"],
    "Cloudflare": ["cloudflare"], "Supabase": ["supabase"], "Neo4j": ["neo4j"],
    "Snowflake": ["snowflake"], "MongoDB Atlas": ["mongodb"],
    "Datadog": ["datadog"], "Sentry": ["sentry"],
    "Notion": ["notion"], "Airtable": ["airtable"], "Linear": ["linear"],
    "Jira": ["jira"], "Asana": ["asana"], "Monday.com": ["monday"],
    "ClickUp": ["clickup"], "Coda": ["coda"], "Smartsheet": ["smartsheet"],
    "Harvest": ["harvest"],
    "Stripe": ["stripe"], "Plaid": ["plaid"], "Binance": ["binance"],
    "QuickBooks": ["quickbooks"], "Xero": ["xero"], "Brex": ["brex"],
    "Ramp": ["ramp"], "PitchBook": ["pitchbook"],
    "NotebookLM": ["notebooklm"], "Otter AI": ["otter"], "Fathom": ["fathom"],
    "Consensus": ["consensus"], "Reducto": ["reducto"], "Devin": ["devin"],
    "Higgsfield": ["higgsfield"], "YouTube Transcript": ["youtube"],
    "Grain": ["grain"],
}


class McpClient:
    """Minimal MCP client over Streamable HTTP (initialize -> tools/call)."""

    def __init__(self, api_key: str):
        self.url = MCP_URL
        self.s = requests.Session()
        self.h = {"Authorization": f"Bearer {api_key}",
                  "Content-Type": "application/json",
                  "Accept": "application/json, text/event-stream"}
        self.sid: str | None = None
        self._id = 0

    def _post(self, payload: dict) -> list[dict]:
        h = dict(self.h)
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        r = self.s.post(self.url, headers=h, json=payload, timeout=120)
        self.sid = r.headers.get("mcp-session-id") or self.sid
        objs = []
        for line in r.text.splitlines():
            if line.startswith("data: "):
                try:
                    objs.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass
        return objs

    def start(self) -> dict:
        self._id += 1
        objs = self._post({"jsonrpc": "2.0", "id": self._id, "method": "initialize",
                           "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                      "clientInfo": {"name": "composio-research-agent",
                                                     "version": "1.0"}}})
        server = objs[0]["result"]["serverInfo"] if objs else {}
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return server

    def call(self, name: str, arguments: dict) -> str:
        self._id += 1
        objs = self._post({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                           "params": {"name": name, "arguments": arguments}})
        for o in objs:
            if o.get("id") == self._id:
                res = o.get("result", {})
                content = res.get("content") or []
                return content[0].get("text", "") if content else ""
        return ""


def _extract_prefixes(text: str) -> dict[str, set[str]]:
    """Parse tool names out of a search response; map prefix -> tool names."""
    prefixes: dict[str, set[str]] = {}
    for tok in TOOL_TOKEN.findall(text):
        if tok.startswith("COMPOSIO_"):
            continue
        prefix = tok.split("_", 1)[0].lower()
        prefixes.setdefault(prefix, set()).add(tok)
    return prefixes


def run_cross_check(records: list[AppRecord]) -> dict:
    key = env("COMPOSIO_API_KEY") or os.environ.get("COMPOSIO_API_KEY", "")
    if not key:
        result = {"status": "no COMPOSIO_API_KEY set - skipped", "overlaps": []}
        _save(result)
        print(f"Composio cross-check: {result['status']}")
        return result

    wanted = {rec.name: SLUG_HINTS.get(rec.name, []) for rec in records
              if SLUG_HINTS.get(rec.name)}
    try:
        client = McpClient(key)
        server = client.start()
        print(f"Composio MCP connected: {server.get('name', '?')} (session {str(client.sid)[:8]}…)")
    except Exception as e:
        result = {"status": f"MCP connection failed: {type(e).__name__}: {str(e)[:120]}",
                  "overlaps": []}
        _save(result)
        print(f"Composio cross-check: {result['status']}")
        return result

    names = list(wanted)
    found: dict[str, dict] = {}
    for ai, name in enumerate(names):
        text = ""
        for attempt in (1, 2, 3):
            try:
                text = client.call("COMPOSIO_SEARCH_TOOLS",
                                   {"queries": [{"use_case": name}]})
                break
            except Exception as e:
                if attempt == 3:
                    print(f"  {name}: failed after 3 attempts ({str(e)[:80]})")
                    continue
                time.sleep(2 * attempt)
        prefixes = _extract_prefixes(text)
        for h in wanted[name]:
            h_norm = h.replace("-", "").replace("_", "")
            hit = next((p for p in prefixes if h_norm in p), None)
            if hit:
                tools = sorted(prefixes[hit])
                found[name] = {"prefix": hit, "n_tools": len(tools),
                               "sample_tools": tools[:3]}
                break
        if (ai + 1) % 15 == 0:
            print(f"  progress {ai + 1}/{len(names)} apps searched, {len(found)} matched")
        time.sleep(CALL_GAP_S)

    overlaps = [{"name": k, "composio_prefix": v["prefix"],
                 "n_tools": v["n_tools"], "sample_tools": v["sample_tools"]}
                for k, v in sorted(found.items(), key=lambda kv: -kv[1]["n_tools"])]
    result = {
        "status": f"ok: MCP gateway queried for {len(names)} apps "
                  f"({len(found)} matched)",
        "transport": "MCP (connect.composio.dev/mcp) via COMPOSIO_SEARCH_TOOLS",
        "server": server.get("name"),
        "apps_searched": len(names),
        "overlaps_with_our_100": len(overlaps),
        "overlaps": overlaps,
    }
    _save(result)
    print(f"Composio cross-check: {len(overlaps)}/{len(names)} apps have Composio toolkits "
          f"(top: {', '.join(o['name'] + ' [' + str(o['n_tools']) + ']' for o in overlaps[:6])})")
    return result


def _save(result: dict) -> None:
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / "composio_toolbelt.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    from io_utils import load_records

    load_dotenv(ROOT / ".env")
    run_cross_check(load_records())
