"""Apply human-promoted overrides to the draft -> pass 2 dataset.

data/overrides.csv is the ledger of corrections the verification loop +
deep-dive produced and the human accepted. Nothing in the pipeline edits
it automatically - promotion is always a human decision (that is the
documented human-in-the-loop).

    python src/apply.py
"""
from __future__ import annotations

from config import DRAFT_CSV, OVERRIDES_CSV, PASS2_CSV
from io_utils import load_overrides, read_csv, write_csv


def apply() -> tuple[int, int]:
    rows = {int(r["id"]): dict(r) for r in read_csv(DRAFT_CSV)}
    overrides = load_overrides()
    applied = 0
    for ov in overrides:
        rid, field = int(ov["id"]), ov["field"]
        if rid in rows and field in rows[rid]:
            rows[rid][field] = ov["value"]
            applied += 1
    ordered = [rows[i] for i in sorted(rows)]
    write_csv(PASS2_CSV, ordered)
    print(f"pass 2: {applied} field overrides over {len(ordered)} rows "
          f"-> {PASS2_CSV.name}")
    return applied, len(overrides)


if __name__ == "__main__":
    apply()
