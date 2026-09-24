"""Build the overrides ledger: every correction between pass 1 and pass 2.

For each field where the verified corpus (data/verified.csv) differs from
the untouched draft (out/draft_pass1.csv), emit a labeled override row.
The label records HOW the correction was established:

  agent-report    an app-research agent verified this app live (fetched docs)
  agent-deep-dive the deep-dive stage fetched docs + extracted, human confirmed
  human-review    settled during reviewer reconciliation (conflicts, judgment)

data/overrides.csv is committed; apply.py replays it on any future draft so
pass 2 is deterministic.

    python src/make_overrides.py
"""
from __future__ import annotations

import json

from config import (DRAFT_CSV, OVERRIDES_CSV, OUT, REPORTS, VERIFIED_CSV)
from io_utils import read_csv, write_csv

FIELDS = ("does", "auth", "auth_detail", "gate", "gate_detail", "surface",
          "breadth", "mcp", "mcp_evidence", "verdict", "blocker", "evidence",
          "confidence", "notes")


def main() -> None:
    draft = {int(r["id"]): r for r in read_csv(DRAFT_CSV)}
    verified = {int(r["id"]): r for r in read_csv(VERIFIED_CSV)}

    # which apps were covered by a live agent report?
    agent_ids: set[int] = set()
    for f in REPORTS.glob("*.json"):
        if f.name.startswith("mcp_sweep"):
            continue
        try:
            for rec in json.loads(f.read_text(encoding="utf-8")):
                agent_ids.add(int(rec["id"]))
        except (ValueError, json.JSONDecodeError):
            continue
    deepdive_ids = set()
    for r in read_csv(OUT.parent / "data" / "research_drafts.csv"):
        try:
            deepdive_ids.add(int(r["id"]))
        except ValueError:
            continue

    rows = []
    for rid in sorted(verified):
        v, d = verified[rid], draft.get(rid, {})
        for f in FIELDS:
            old = str(d.get(f, "")).strip()
            new = str(v.get(f, "")).strip()
            if old == new:
                continue
            if rid in agent_ids:
                src = "agent-report"
                note = "app-research agent verified live (docs fetched)"
            elif rid in deepdive_ids:
                src = "agent-deep-dive"
                note = "deep-dive extraction, confirmed by reviewer"
            else:
                src = "human-review"
                note = "reviewer reconciliation (stable docs knowledge)"
            rows.append({"id": rid, "app": v.get("name", ""), "field": f,
                         "draft_value": old, "value": new, "source": src,
                         "note": note})

    write_csv(OVERRIDES_CSV, rows,
              ["id", "app", "field", "draft_value", "value", "source", "note"])
    from collections import Counter
    print(f"overrides: {len(rows)} field corrections over "
          f"{len({r['id'] for r in rows})} apps -> {OVERRIDES_CSV.name}")
    print("  by source:", dict(Counter(r["source"] for r in rows)))
    print("  by field:", dict(Counter(r["field"] for r in rows).most_common(5)))


if __name__ == "__main__":
    main()
