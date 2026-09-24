"""Shared vocabulary, paths and tunables for the research pipeline.

Every stage speaks the same controlled vocabulary, so verification,
overrides, auditing and rendering can compare fields mechanically.
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DATA = ROOT / "data"
OUT = ROOT / "out"
SRC = ROOT / "src"

# ---------------------------------------------------------------- files
APPS_CSV = DATA / "apps.csv"              # roster: id, name, category, website
VERIFIED_CSV = DATA / "verified.csv"      # final reviewed dataset (pass 2 source)
DRAFT_CSV = OUT / "draft_pass1.csv"       # agent's memory-only first pass
DRAFT_META = OUT / "draft_pass1_meta.json"
PASS2_CSV = OUT / "apps_pass2.csv"        # draft + promoted overrides
VERIFY_JSON = {1: OUT / "verification_pass1.json", 2: OUT / "verification_pass2.json"}
RESEARCH_DRAFTS = DATA / "research_drafts.csv"   # agent proposals (status=draft)
OVERRIDES_CSV = DATA / "overrides.csv"    # human-promoted corrections
AUDIT_CSV = DATA / "audit_sample.csv"     # independent ground-truth sample
AUDIT_JSON = {1: OUT / "audit_pass1.json", 2: OUT / "audit_pass2.json"}
PATTERNS_JSON = OUT / "patterns.json"
COMPOSIO_JSON = OUT / "composio_toolbelt.json"
REPORT_JSON = OUT / "research_report.json"  # machine-readable mirror of the page
INDEX_HTML = ROOT / "index.html"

# ------------------------------------------------------- vocabularies
AUTH_METHODS = ("OAuth2", "API key", "Basic", "Token", "HMAC", "None", "Other")
GATING = ("Open self-serve", "Paid self-serve", "Admin approval",
          "Contact sales / partner", "N/A (no auth)")
SURFACE = ("Documented REST", "Documented GraphQL", "REST + GraphQL",
           "SDK/API limited", "No public API")
VERDICTS = ("Ready", "Ready with caveats", "Blocked")
MCP = ("Yes (official)", "Yes (community)", "No", "Unclear")

# fields the audit scores against ground truth
SCORED_FIELDS = ("auth", "gate", "surface", "mcp", "verdict")

# ------------------------------------------------------------- tuning
HTTP_TIMEOUT = 25            # seconds per evidence fetch
HTTP_CONCURRENCY = 12        # evidence checks run in a thread pool
MAX_EVIDENCE_BYTES = 400_000  # truncate fetched docs before sniffing
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_BATCH = 10            # apps per draft call
GEMINI_TIMEOUT = 120         # seconds per call
GEMINI_RETRIES = 2

CATEGORY_ORDER = (
    "CRM & Sales", "Support & Helpdesk", "Communications & Messaging",
    "Marketing & Ads", "Ecommerce", "Data, SEO & Scraping",
    "Developer & Infra", "Productivity & PM", "Finance & Fintech",
    "AI, Research & Media",
)
