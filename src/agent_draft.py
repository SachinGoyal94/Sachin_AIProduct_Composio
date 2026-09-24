"""Pass 1 — the agent's memory-only draft.

The LLM drafts auth / gating / API surface / MCP / verdict for all 100
apps from its own knowledge, with NO web access. This is the honest
"first pass" the verification loop later improves. When GEMINI_API_KEY
is absent, a previously committed draft is reused so the run stays
reproducible offline.

    python src/agent_draft.py            # draft all 100 (needs key, cached)
    python src/agent_draft.py --fresh    # ignore cache, re-query
"""
from __future__ import annotations

import datetime as dt
import sys

import llm
from config import APPS_CSV, DRAFT_CSV, DRAFT_META, GEMINI_BATCH, GEMINI_MODEL
from io_utils import apps_to_rows, read_csv, write_csv, write_json

VOCAB = f"""auth: one of OAuth2 | API key | Basic | Token | HMAC | None | Other
gate: one of Open self-serve | Paid self-serve | Admin approval | Contact sales / partner | N/A (no auth)
surface: one of Documented REST | Documented GraphQL | REST + GraphQL | SDK/API limited | No public API
mcp: one of Yes (official) | Yes (community) | No | Unclear
verdict: one of Ready | Ready with caveats | Blocked"""

SYSTEM = (
    "You are a API-integration researcher. You get a batch of SaaS apps. "
    "From your own knowledge only (you have NO web access), draft for each app: "
    "what it does (one line), its primary API auth method, how a developer obtains "
    "credentials (gating), the documented API surface and rough breadth, whether an "
    "MCP server exists, and whether an agent toolkit could be built today.\n"
    f"Use EXACTLY this controlled vocabulary:\n{VOCAB}\n"
    "Give your best docs URL as evidence. Set confidence 1-5 honestly (1=guessing, "
    "5=you are certain). Non-Ready verdicts need a short blocker. Reply with ONLY a "
    "JSON array, one object per app, fields: id, does, auth, auth_detail, gate, "
    "gate_detail, surface, breadth, mcp, verdict, blocker, evidence, confidence."
)


def draft_all(fresh: bool) -> list[dict]:
    apps = read_csv(APPS_CSV)
    rows: dict[int, dict] = {}
    calls = 0
    for i in range(0, len(apps), GEMINI_BATCH):
        batch = apps[i:i + GEMINI_BATCH]
        listing = "\n".join(
            f'id={a["id"]} | {a["name"]} | category={a["category"]} | site={a["website"]}'
            for a in batch)
        prompt = (f"Draft records for these {len(batch)} apps.\n{listing}\n"
                  f"Return a JSON array of {len(batch)} objects.")
        text = llm.call(prompt, system=SYSTEM, use_cache=not fresh)
        calls += 1
        try:
            got = llm.parse_json(text)
        except Exception as e:  # noqa: BLE001
            print(f"  batch {i}-{i+len(batch)-1}: unparseable ({e}) - skipped")
            continue
        for rec in got:
            try:
                rows[int(rec["id"])] = rec
            except (KeyError, TypeError, ValueError):
                continue
        print(f"  batch {i + 1}-{i + len(batch)}: {len(got)} drafts")

    merged = []
    for a in apps:
        d = rows.get(int(a["id"]), {})
        merged.append({
            "id": a["id"], "name": a["name"], "category": a["category"],
            "website": a["website"],
            "does": d.get("does", ""), "auth": d.get("auth", ""),
            "auth_detail": d.get("auth_detail", ""), "gate": d.get("gate", ""),
            "gate_detail": d.get("gate_detail", ""), "surface": d.get("surface", ""),
            "breadth": d.get("breadth", ""), "mcp": d.get("mcp", ""),
            "mcp_evidence": d.get("mcp_evidence", ""),
            "verdict": d.get("verdict", ""), "blocker": d.get("blocker", ""),
            "evidence": d.get("evidence", ""),
            "confidence": d.get("confidence", 1),
            "notes": d.get("notes", ""),
        })
    meta = {
        "model": GEMINI_MODEL, "calls": calls, "rows": len(merged),
        "mode": "memory-only (no web access)",
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "fresh": bool(fresh),
    }
    write_csv(DRAFT_CSV, merged)
    write_json(DRAFT_META, meta)
    print(f"draft pass 1: {len(merged)} rows -> {DRAFT_CSV.name} ({calls} calls, "
          f"model={GEMINI_MODEL})")
    return merged


def main() -> None:
    fresh = "--fresh" in sys.argv
    if not llm.available():
        if DRAFT_CSV.exists():
            print("GEMINI_API_KEY missing - reusing committed draft_pass1.csv")
            return
        sys.exit("GEMINI_API_KEY missing and no cached draft present. "
                 "Set the key or run with a committed draft for offline mode.")
    draft_all(fresh)


if __name__ == "__main__":
    main()
