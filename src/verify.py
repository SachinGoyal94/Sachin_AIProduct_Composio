"""Live verification loop — checks every row of a pass against the web.

Two layers:
  1. Evidence liveness: HTTP-fetch each row's docs URL. Records status,
     redirects, and whether the fetched page actually talks like API docs
     (mentions of oauth / api key / bearer / authorization / endpoints).
  2. Rule engine: vocabulary + cross-field contradiction checks that no
     amount of HTTP can prove (e.g. "No public API" but verdict "Ready").

Flags feed research.py (deep-dive) and the accuracy story on the page.

    python src/verify.py 1    # verify the draft (pass 1)
    python src/verify.py 2    # verify pass 2 (draft + overrides)
"""
from __future__ import annotations

import concurrent.futures as cf
import re
import sys
from urllib.parse import urlparse

import requests

from config import (DRAFT_CSV, HTTP_CONCURRENCY, HTTP_TIMEOUT,
                    MAX_EVIDENCE_BYTES, PASS2_CSV, VERIFY_JSON,
                    AUTH_METHODS, GATING, MCP, SURFACE, VERDICTS)
from io_utils import read_csv, split_evidence, write_json

DOCS_HINTS = ("docs", "developer", "developers", "api", "reference",
              "/documentation", "dev.")
API_WORDS = re.compile(
    r"oauth|api[_ -]?key|bearer|authorization|access[_ -]?token|"
    r"endpoints?|rest api|graphql|authentication", re.I)


def check_url(url: str) -> dict:
    if not urlparse(url).scheme:
        url = "https://" + url.lstrip("/")
    out = {"url": url, "status": 0, "final_url": url, "redirected": False,
           "ok": False, "docs_like": False, "error": ""}
    try:
        r = requests.get(url, timeout=HTTP_TIMEOUT, stream=True,
                         headers={"User-Agent": "Mozilla/5.0 (research-bot; "
                                  "+case-study evidence check)"}, allow_redirects=True)
        out["status"] = r.status_code
        out["final_url"] = r.url
        out["redirected"] = str(r.url) != url
        text = b""
        for chunk in r.iter_content(32_768):
            text += chunk
            if len(text) >= MAX_EVIDENCE_BYTES:
                break
        r.close()
        out["ok"] = 200 <= r.status_code < 300
        body = text.decode("utf-8", "ignore")
        out["docs_like"] = bool(API_WORDS.search(body[:200_000]))
    except requests.RequestException as e:
        out["error"] = f"{type(e).__name__}: {e}"[:160]
    return out


def looks_like_docs(url: str) -> bool:
    host = urlparse(url).netloc.lower() + urlparse(url).path.lower()
    return any(h in host for h in DOCS_HINTS)


def rule_check(row: dict) -> list[str]:
    flags = []
    ev = split_evidence(row)
    if not ev:
        flags.append("no-evidence-url")
    elif not any(looks_like_docs(u) for u in ev):
        flags.append("evidence-not-docs-host")
    # controlled-vocabulary compliance (first-pass drafts drift)
    for f, vocab in (("auth", AUTH_METHODS), ("gate", GATING),
                     ("surface", SURFACE), ("mcp", MCP), ("verdict", VERDICTS)):
        if row.get(f) and row[f] not in vocab:
            flags.append(f"vocab:{f}")
    if row.get("surface") == "No public API" and row.get("verdict") == "Ready":
        flags.append("contradiction:no-api-but-ready")
    if row.get("gate") == "N/A (no auth)" and row.get("surface") != "No public API":
        flags.append("contradiction:no-auth-but-api")
    if row.get("gate") in ("Open self-serve", "Paid self-serve") \
            and row.get("verdict") == "Blocked" \
            and "no public api" not in (row.get("blocker") or "").lower():
        flags.append("contradiction:self-serve-but-blocked")
    if row.get("gate") == "Contact sales / partner" and row.get("verdict") == "Ready" \
            and not row.get("blocker"):
        flags.append("contradiction:gated-but-ready")
    if row.get("auth") == "None" and row.get("surface") not in ("", "No public API"):
        flags.append("contradiction:auth-none-but-api")
    try:
        if int(row.get("confidence") or 0) <= 2:
            flags.append("low-confidence")
    except ValueError:
        flags.append("bad-confidence")
    if not row.get("does"):
        flags.append("missing-description")
    return flags


def verify_pass(n: int, csv_path) -> dict:
    rows = read_csv(csv_path)
    urls = sorted({u for r in rows for u in split_evidence(r)})
    print(f"pass {n}: {len(rows)} rows, {len(urls)} distinct evidence URLs")
    with cf.ThreadPoolExecutor(HTTP_CONCURRENCY) as ex:
        checks = dict(zip(urls, ex.map(check_url, urls)))

    per_row, n_live, n_dead = [], 0, 0
    for r in rows:
        evs = [dict(checks[u]) for u in split_evidence(r)]
        live = [c for c in evs if c["ok"]]
        if evs:
            n_live += 1 if any(c["ok"] for c in evs) else 0
            n_dead += 0 if any(c["ok"] for c in evs) else 1
        r_flags = rule_check(r)
        if evs and not any(c["ok"] for c in evs):
            r_flags.append("dead-evidence")
        elif evs and not any(c["docs_like"] and c["ok"] for c in evs):
            r_flags.append("evidence-not-doc-like")
        per_row.append({"id": int(r["id"]), "name": r["name"],
                        "evidence": evs, "flags": r_flags})

    flagged = [p for p in per_row if p["flags"]]
    result = {
        "pass": n,
        "rows": len(rows),
        "evidence_urls": len(urls),
        "rows_with_live_evidence": n_live,
        "rows_with_dead_evidence": n_dead,
        "flagged_rows": len(flagged),
        "clean_rows": len(rows) - len(flagged),
        "flag_counts": _counts(f for p in per_row for f in p["flags"]),
        "per_row": per_row,
    }
    write_json(VERIFY_JSON[n], result)
    print(f"  live evidence: {n_live}/{len(rows)} rows | dead: {n_dead} | "
          f"flagged: {len(flagged)} -> {VERIFY_JSON[n].name}")
    return result


def _counts(items) -> dict:
    out: dict[str, int] = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def main() -> None:
    n = sys.argv[1] if len(sys.argv) > 1 else "1"
    csv_path = DRAFT_CSV if n == "1" else PASS2_CSV
    verify_pass(int(n), csv_path)


if __name__ == "__main__":
    main()
