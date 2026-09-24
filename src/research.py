"""Deep-dive stage: for rows the verification loop flagged, fetch the real
docs pages and have the LLM extract facts strictly from that evidence.

Proposals land in data/research_drafts.csv with status=draft. They are
NEVER auto-applied: a human reviews them and promotes the accepted ones
into data/overrides.csv. That review step is the documented
human-in-the-loop of this pipeline.

    python src/research.py            # deep-dive all flagged rows (live)
    python src/research.py --limit 10 # only the 10 most-flagged rows
"""
from __future__ import annotations

import datetime as dt
import re
import sys

import requests
from bs4 import BeautifulSoup

import llm
from config import (DRAFT_CSV, HTTP_TIMEOUT, RESEARCH_DRAFTS, VERIFY_JSON)
from io_utils import read_csv, write_csv

SYSTEM = (
    "You are a precise API-research analyst. You get the raw text of a vendor's "
    "official documentation page(s) for one app, plus the app name. Extract ONLY "
    "what the text supports; where the text is silent, answer \"Unclear\". "
    "Reply with ONLY a JSON object with keys: auth (one of OAuth2|API key|Basic|"
    "Token|HMAC|None|Other|Unclear), auth_detail, gate (one of Open self-serve|"
    "Paid self-serve|Admin approval|Contact sales / partner|N/A (no auth)|Unclear), "
    "gate_detail, surface (one of Documented REST|Documented GraphQL|REST + GraphQL|"
    "SDK/API limited|No public API|Unclear), breadth, mcp (Yes (official)|"
    "Yes (community)|No|Unclear), verdict (Ready|Ready with caveats|Blocked|Unclear), "
    "blocker, quotes (array of up to 3 short verbatim quotes from the text that "
    "support your answers)."
)

FIELD_MAP = {"auth", "auth_detail", "gate", "gate_detail", "surface", "breadth",
             "mcp", "verdict", "blocker"}


def fetch_text(url: str, limit: int = 14_000) -> str:
    try:
        r = requests.get(url, timeout=HTTP_TIMEOUT,
                         headers={"User-Agent": "Mozilla/5.0 (research-bot)"})
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "svg"]):
            tag.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        return text[:limit]
    except requests.RequestException:
        return ""


def deep_dive(row: dict, urls: list[str], use_llm: bool) -> dict | None:
    corpus = ""
    for u in urls[:2]:
        corpus += f"\n\n=== SOURCE: {u} ===\n" + fetch_text(u)
    if not corpus.strip():
        return None
    proposal = {"source": urls[0], "quotes": ""}
    if use_llm:
        prompt = (f"App: {row['name']} ({row.get('website', '')}).\n"
                  f"Documentation text:\n{corpus[:26_000]}\n"
                  "Extract the JSON object described in the system prompt.")
        try:
            got = llm.parse_json(llm.call(prompt, system=SYSTEM))
        except Exception:  # noqa: BLE001 - network/parse failure: record as blocked
            got = {}
        for k in ("auth", "gate", "surface", "mcp", "verdict"):
            proposal[k] = got.get(k, "Unclear")
        proposal["auth_detail"] = got.get("auth_detail", "")
        proposal["gate_detail"] = got.get("gate_detail", "")
        proposal["breadth"] = got.get("breadth", "")
        proposal["blocker"] = got.get("blocker", "")
        proposal["quotes"] = " || ".join(got.get("quotes", [])[:3])[:600]
        proposal["confidence"] = 4 if got else 1
    return proposal


def main() -> None:
    limit = 0
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    import json
    ver1 = json.loads(VERIFY_JSON[1].read_text()) if VERIFY_JSON[1].exists() else None
    draft = {int(r["id"]): r for r in read_csv(DRAFT_CSV)}
    if not ver1 or not draft:
        sys.exit("need out/verification_pass1.json and out/draft_pass1.csv first")

    flagged = [p for p in ver1["per_row"] if p["flags"]]
    if limit:
        flagged = sorted(flagged, key=lambda p: -len(p["flags"]))[:limit]
    use_llm = llm.available()
    if not use_llm:
        print("GEMINI_API_KEY missing: deep-dive will only fetch + log sources")

    existing = {r["id"]: r for r in read_csv(RESEARCH_DRAFTS)}
    n_new = 0
    for p in flagged:
        rid = str(p["id"])
        if rid in existing and existing[rid].get("status") == "promoted":
            continue  # human already handled this one
        row = draft[p["id"]]
        urls = [c["url"] for c in p["evidence"] if c.get("url")]
        prop = deep_dive(row, urls, use_llm)
        if prop is None:
            proposal = {**{k: "" for k in ("auth", "auth_detail", "gate", "gate_detail",
                                           "surface", "breadth", "mcp", "verdict",
                                           "blocker", "quotes")},
                        "id": rid, "app": row["name"], "confidence": 1,
                        "source": urls[0] if urls else "", "status": "draft",
                        "note": "fetch failed - needs manual research"}
        else:
            proposal = {"id": rid, "app": row["name"], **prop, "status": "draft",
                        "note": "auto-proposed from fetched docs; human review pending"}
        existing[rid] = proposal
        n_new += 1
        print(f"  #{rid} {row['name']}: "
              f"{proposal.get('verdict', '?')} / {proposal.get('auth', '?')}")

    ordered = sorted(existing.values(), key=lambda r: int(r["id"]))
    fieldnames = ["id", "app", "auth", "auth_detail", "gate", "gate_detail",
                  "surface", "breadth", "mcp", "verdict", "blocker", "source",
                  "quotes", "confidence", "status", "note"]
    write_csv(RESEARCH_DRAFTS, ordered, fieldnames)
    print(f"research drafts: {n_new} new proposals, {len(ordered)} total "
          f"-> {RESEARCH_DRAFTS.name}")
    print("human step: review data/research_drafts.csv, promote accepted "
          "corrections into data/overrides.csv, then run apply.py")


if __name__ == "__main__":
    main()
