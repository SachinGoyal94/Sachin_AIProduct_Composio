"""Assemble out/research_report.json - the machine-readable mirror of the
case-study page. Agents and reviewers can consume this instead of parsing
HTML; the page embeds the exact same payload.

    python src/report.py
"""
from __future__ import annotations

import datetime as dt

from config import (AUDIT_JSON, COMPOSIO_JSON, DRAFT_CSV, DRAFT_META,
                    OVERRIDES_CSV, PASS2_CSV, PATTERNS_JSON, REPORT_JSON,
                    RESEARCH_DRAFTS, VERIFY_JSON)
from io_utils import read_csv, read_json, write_json


def build() -> dict:
    patterns = read_json(PATTERNS_JSON)
    ver1 = read_json(VERIFY_JSON[1])
    ver2 = read_json(VERIFY_JSON[2])
    aud1 = read_json(AUDIT_JSON[1])
    aud2 = read_json(AUDIT_JSON[2])
    verified = read_csv(PASS2_CSV)
    drafts = read_csv(RESEARCH_DRAFTS)
    overrides = read_csv(OVERRIDES_CSV)

    audit_public = []
    for aud in (aud1, aud2):
        audit_public.append({
            "pass": aud["pass"], "sample_size": aud["sample_size"],
            "fields_scored": aud["fields_scored"],
            "field_accuracy": aud["field_accuracy"],
            "row_accuracy": aud["row_accuracy"],
            "misses": [
                {"id": a["id"], "name": a["name"], "category": a["category"],
                 "misses": [
                     {"field": f["field"], "expected": f["expected"],
                      "actual": f["actual"]} for f in a["fields"] if not f["ok"]
                 ]}
                for a in aud["per_app"] if not a["all_ok"]
            ],
        })

    ver_public = []
    for ver in (ver1, ver2):
        ver_public.append({
            "pass": ver["pass"], "rows": ver["rows"],
            "evidence_urls": ver["evidence_urls"],
            "rows_with_live_evidence": ver["rows_with_live_evidence"],
            "rows_with_dead_evidence": ver["rows_with_dead_evidence"],
            "flagged_rows": ver["flagged_rows"],
            "clean_rows": ver["clean_rows"],
            "flag_counts": ver["flag_counts"],
        })

    composio = read_json(COMPOSIO_JSON) if COMPOSIO_JSON.exists() else {}

    payload = {
        "schema": "composio-case-study/1.0",
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "meta": {
            "apps": len(verified),
            "categories": 10,
            "draft_meta": read_json(DRAFT_META) if DRAFT_META.exists() else {},
            "overrides_promoted": len(overrides),
            "research_proposals": len(drafts),
            "claim": ("Every number on the page is computed from the pipeline "
                      "artifacts; this JSON mirrors the page for agents."),
        },
        "verification": ver_public,
        "audit": audit_public,
        "patterns": patterns,
        "composio": composio,
        "human_in_the_loop": {
            "proposals_file": "data/research_drafts.csv",
            "overrides_file": "data/overrides.csv",
            "note": ("research.py never auto-applies corrections; a human "
                     "reviews proposals and promotes them to overrides.csv"),
        },
        "dataset": verified,
    }
    write_json(REPORT_JSON, payload)
    print(f"report: {len(verified)} apps, audit "
          f"{aud1['field_accuracy']:.0%}->{aud2['field_accuracy']:.0%} "
          f"-> {REPORT_JSON.name}")
    return payload


if __name__ == "__main__":
    build()
