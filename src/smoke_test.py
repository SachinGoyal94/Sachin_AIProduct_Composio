"""Self-verification: assert every invariant the case study depends on.

Run as the pipeline's final stage (or standalone) - it re-checks what the
page claims against the artifacts, so a regression anywhere fails loudly
instead of silently producing a wrong page.

    python src/smoke_test.py
"""
from __future__ import annotations

import json
import sys

from config import (AUDIT_CSV, AUDIT_JSON, COMPOSIO_JSON, DRAFT_CSV,
                    INDEX_HTML, OVERRIDES_CSV, PASS2_CSV, PATTERNS_JSON,
                    REPORT_JSON, SCORED_FIELDS, VERIFY_JSON)
from io_utils import check_vocabulary, load_verified, read_csv, read_json

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def main() -> None:
    print("smoke test - verifying every invariant behind the page:")

    # 1. dataset shape
    verified = load_verified()
    check("dataset has exactly 100 rows", len(verified) == 100)
    check("ids are contiguous 1..100",
          [a.id for a in verified] == list(range(1, 101)))
    vocab_bad = [(a.id, b) for a in verified for b in check_vocabulary(a)]
    check("every row obeys the controlled vocabulary", not vocab_bad, str(vocab_bad[:3]))
    check("every row carries evidence",
          all(a.evidence.strip() for a in verified),
          str([a.id for a in verified if not a.evidence.strip()][:5]))
    check("every row carries a one-liner",
          all(a.does.strip() for a in verified))

    # 2. drafts + overrides ledger
    draft = read_csv(DRAFT_CSV)
    check("pass-1 draft preserved (100 rows)", len(draft) == 100)
    ov = read_csv(OVERRIDES_CSV)
    check("overrides ledger non-empty", len(ov) > 0, f"{len(ov)} rows")
    check("override fields are all real fields",
          all(o["field"] in {"does", "auth", "auth_detail", "gate", "gate_detail",
                             "surface", "breadth", "mcp", "mcp_evidence", "verdict",
                             "blocker", "evidence", "confidence", "notes", "quotes"}
              for o in ov))
    check("every override carries a source label",
          all(o.get("source") in ("agent-report", "agent-deep-dive", "human-review")
              for o in ov))

    # 3. audit consistency (the headline numbers)
    aud1 = read_json(AUDIT_JSON[1])
    aud2 = read_json(AUDIT_JSON[2])
    check("audit sample is 20 apps", aud1["sample_size"] == 20 == aud2["sample_size"])
    check("audit grades 100 fields per pass",
          aud1["fields_scored"] == 100 == aud2["fields_scored"])
    check("pass 2 accuracy >= pass 1",
          aud2["field_accuracy"] >= aud1["field_accuracy"])
    check("audit math is internally consistent",
          aud1["field_accuracy"] == round(aud1["fields_correct"] / aud1["fields_scored"], 4)
          and aud2["field_accuracy"] == round(aud2["fields_correct"] / aud2["fields_scored"], 4))

    # 4. verification liveness
    ver2 = read_json(VERIFY_JSON[2])
    reachable = (ver2["rows_with_live_evidence"] + ver2.get("rows_bot_blocked", 0))
    check(">=98/100 rows have reachable evidence", reachable >= 98,
          f"{reachable}")
    check("pass-2 flags never exceed pass-1 flags",
          ver2["flagged_rows"] <= read_json(VERIFY_JSON[1])["flagged_rows"])

    # 5. patterns + composio
    pat = read_json(PATTERNS_JSON)
    check("patterns cover 100 apps", pat["n_apps"] == 100)
    check("headline claims all carry metrics",
          all(h.get("metric") for h in pat["headline"]))
    ids = {a.id for a in verified}
    check("easy wins reference real apps",
          all(w["id"] in ids for w in pat["easy_wins"]))
    try:
        comp = read_json(COMPOSIO_JSON)
        check("composio cross-check ran over all 100 apps",
              comp.get("ok") and len(comp.get("apps", [])) == 100)
    except FileNotFoundError:
        check("composio cross-check artifact exists", False, "missing")

    # 6. report mirror + page
    rep = read_json(REPORT_JSON)
    check("report mirrors the full dataset", len(rep.get("dataset", [])) == 100)
    check("report carries both audit passes",
          len(rep.get("audit", [])) == 2)
    page = INDEX_HTML.read_text(encoding="utf-8")
    check("page embeds the dataset JSON", 'id="report-data"' in page)
    check("page shows the audit delta",
          f"{aud1['field_accuracy'] * 100:.0f}% to {aud2['field_accuracy'] * 100:.0f}%"
          .lower() in page.lower())
    check("page links the machine-readable mirror", "out/research_report.json" in page)

    # 7. audit sample sources are clickable
    sample = read_csv(AUDIT_CSV)
    check("every ground-truth row cites a source URL",
          all(s.get("source", "").startswith("http") for s in sample))

    print(f"\n{'ALL CHECKS PASSED' if not FAILURES else str(len(FAILURES)) + ' FAILURES'}")
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
