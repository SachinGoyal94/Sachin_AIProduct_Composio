"""Config: paths, taxonomy and HTTP helper used across the pipeline.

Single source of truth for field vocabularies so the classifier, verifier
and renderer all speak the same language.
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "out"
UA = "ComposioTakehomeAgent/1.0 (research pipeline; contact: applicant)"

CATEGORIES = [
    "CRM and Sales",
    "Support and Helpdesk",
    "Communications and Messaging",
    "Marketing, Ads, Email and Social",
    "Ecommerce",
    "Data, SEO and Scraping",
    "Developer, Infra and Data platforms",
    "Productivity and Project Management",
    "Finance and Fintech",
    "AI, Research and Media-native",
]

# CSV stores the compact category label used in data/apps.csv
CATEGORY_ALIASES = {
    "Marketing Ads Email Social": "Marketing, Ads, Email and Social",
    "Data SEO and Scraping": "Data, SEO and Scraping",
    "Developer Infra Data": "Developer, Infra and Data platforms",
    "Productivity PM": "Productivity and Project Management",
    "AI Research Media": "AI, Research and Media-native",
}

AUTH_METHODS = [
    "OAuth2",
    "API key",
    "Basic",
    "Bearer token",
    "OAuth1",
    "JWT",
    "HMAC",
    "None",
]
# Accepted spellings that normalize into the canonical list above
AUTH_ALIASES = {
    "api key": "API key",
    "apikey": "API key",
    "api-key": "API key",
    "bearer": "Bearer token",
    "token": "Bearer token",
    "pat": "Bearer token",
    "personal access token": "Bearer token",
    "access token": "Bearer token",
    "session token": "Bearer token",
    "basic auth": "Basic",
    "http basic": "Basic",
    "oauth 2.0": "OAuth2",
    "oauth2 + pkce": "OAuth2",
    "oauth 1.0a": "OAuth1",
    "none (open api)": "None",
    "none (public)": "None",
}

GATING = ["Self-serve", "Self-serve (paid)", "Gated", "Open"]

SURFACE = ["Full REST", "Narrow REST", "GraphQL", "None documented", "SDK/CLI only"]

VERDICTS = ["Ready", "Ready with caveats", "Blocked"]

CONF_LIMIT = 3  # evidence hits below this -> flagged for human pass


@dataclass
class AppRecord:
    id: int
    name: str
    category: str
    does: str
    auth: str
    gate: str
    surface: str
    breadth: str
    mcp: str
    verdict: str
    blocker: str
    evidence: str
    confidence: int
    notes: str = ""

    def canonical_category(self) -> str:
        return CATEGORY_ALIASES.get(self.category, self.category)

    def to_row(self) -> dict:
        d = self.__dict__.copy()
        d["category"] = self.canonical_category()
        return d


def load_apps(path: Path | None = None) -> list[dict]:
    """Load the seed list of 100 apps from CSV."""
    path = path or (DATA / "apps.csv")
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["id"] = int(r["id"])
    assert len(rows) == 100, f"expected 100 apps, got {len(rows)}"
    return rows


def http_get(url: str, timeout: float = 6.0) -> tuple[int, str]:
    """GET a URL with browser-ish headers; returns (status, text[:80_000])."""
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 " + UA,
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        return resp.status_code, resp.text[:80_000]
    except requests.RequestException as e:
        return 0, f"__ERROR__ {type(e).__name__}: {e}"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)
