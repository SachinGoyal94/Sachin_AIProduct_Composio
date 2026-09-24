"""Pass runner: knowledge core (+overrides) -> dataset CSV + flag list.

Usage:
    python analyze.py          # Pass 1
    python analyze.py 2        # Pass 2 (after overrides.csv is populated)
"""
from __future__ import annotations

import sys

from config import CONF_LIMIT
from io_utils import apply_overrides, load_records, save_csv, save_json


def run(pass_no: int = 1) -> None:
    # Pass 1 = pristine knowledge core (no corrections); Pass 2 = after overrides.
    if pass_no >= 2:
        records, n_ovr = apply_overrides(load_records())
    else:
        records, n_ovr = load_records(), 0
    rows = [r.to_row() for r in records]
    save_csv(rows, f"apps_pass{pass_no}.csv")
    flagged = [r.to_row() for r in records if r.confidence < CONF_LIMIT]
    save_json(
        {
            "pass": pass_no,
            "overrides_applied": n_ovr,
            "confidence_limit": CONF_LIMIT,
            "n_flagged": len(flagged),
            "flagged_ids": [r["id"] for r in flagged],
        },
        f"pass{pass_no}_flags.json",
    )
    print(f"Pass {pass_no}: {len(rows)} apps -> out/apps_pass{pass_no}.csv | "
          f"{len(flagged)} flagged (confidence < {CONF_LIMIT}) | overrides applied: {n_ovr}")
    for r in flagged:
        print(f"  - #{r['id']:3d} {r['name']} (conf={r['confidence']})")


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
