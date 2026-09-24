"""Ground-truth audit: strict field-level scoring of a pass.

data/audit_sample.csv holds an independent, hand-verified sample (with its
own expected values and source URLs, fixed before the audit). The same
scorer grades pass 1 and pass 2, which is what makes the accuracy delta
comparable.

    python src/audit.py 1    # grade the draft
    python src/audit.py 2    # grade draft + overrides
"""
from __future__ import annotations

import sys

from config import AUDIT_CSV, AUDIT_JSON, DRAFT_CSV, PASS2_CSV, SCORED_FIELDS
from io_utils import normalize, read_csv, write_json


def grade(n: int, csv_path) -> dict:
    rows = {int(r["id"]): r for r in read_csv(csv_path)}
    sample = read_csv(AUDIT_CSV)
    per_app, fields_total, fields_right, rows_all_right = [], 0, 0, 0
    for s in sample:
        rid = int(s["id"])
        got = rows.get(rid)
        if got is None:
            continue
        fields, rights, misses = [], 0, []
        for f in SCORED_FIELDS:
            expected, actual = s[f], got.get(f, "")
            ok = normalize(expected) == normalize(actual)
            fields.append({"field": f, "expected": expected, "actual": actual,
                           "ok": ok})
            fields_total += 1
            fields_right += ok
            rights += ok
            if not ok:
                misses.append(f)
        all_ok = not misses
        rows_all_right += all_ok
        per_app.append({"id": rid, "name": s["name"], "category": s["category"],
                        "fields": fields, "all_ok": all_ok, "misses": misses,
                        "source": s.get("source", "")})

    result = {
        "pass": n,
        "sample_size": len(per_app),
        "fields_scored": fields_total,
        "field_accuracy": round(fields_right / fields_total, 4) if fields_total else 0,
        "row_accuracy": round(rows_all_right / len(per_app), 4) if per_app else 0,
        "fields_correct": fields_right,
        "rows_fully_correct": rows_all_right,
        "per_app": per_app,
    }
    write_json(AUDIT_JSON[n], result)
    print(f"pass {n} audit: field accuracy {result['field_accuracy']:.1%} "
          f"({fields_right}/{fields_total}) | full-row {result['row_accuracy']:.1%} "
          f"({rows_all_right}/{len(per_app)}) -> {AUDIT_JSON[n].name}")
    return result


def main() -> None:
    n = sys.argv[1] if len(sys.argv) > 1 else "1"
    grade(int(n), DRAFT_CSV if n == "1" else PASS2_CSV)


if __name__ == "__main__":
    main()
