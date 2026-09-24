"""Human-audit harness.

Cross-checks a hand-curated ground-truth sample (data/audit_sample.csv) against
the pipeline's dataset for any pass. Every sampled field is scored as
match / mismatch, so accuracy is computed, not asserted.

Pass 1 scores the pristine knowledge core (pre-override); Pass 2 scores the
final dataset after live research corrections. Expectations in the sample were
pinned to cited source documents during research, not read back from the
dataset - the sample deliberately includes every app the loop corrected.

Usage:  python audit.py [pass_no]
"""
from __future__ import annotations

import csv
import json
import sys

from config import DATA, OUT, AppRecord
from io_utils import apply_overrides, load_records


def _dataset_for_pass(pass_no: int) -> dict[int, AppRecord]:
    records = load_records()
    if pass_no >= 2:
        records, _ = apply_overrides(records)
    return {r.id: r for r in records}


def run_audit(pass_no: int = 2) -> dict:
    with open(DATA / "audit_sample.csv", encoding="utf-8") as f:
        sample = list(csv.DictReader(f))
    dataset = _dataset_for_pass(pass_no)
    results, n_ok = [], 0
    for s in sample:
        rec = dataset[int(s["id"])]
        got = str(getattr(rec, s["field"]))
        ok = got == s["expected"]
        n_ok += ok
        results.append({
            "id": rec.id, "name": rec.name, "field": s["field"],
            "expected": s["expected"], "agent": got,
            "match": ok, "source_of_truth": s["source_of_truth"],
        })
    total = len(results)
    summary = {
        "pass": pass_no, "sample_size": total,
        "matches": n_ok, "accuracy": round(100 * n_ok / total, 1),
        "mismatches": [r for r in results if not r["match"]],
    }
    out = OUT / f"audit_pass{pass_no}.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"PASS {pass_no}: {n_ok}/{total} = {summary['accuracy']}% audit accuracy")
    for m in summary["mismatches"]:
        print(f"  MISMATCH #{m['id']} {m['name']} [{m['field']}]: "
              f"expected={m['expected']} agent={m['agent']}")
    return summary


if __name__ == "__main__":
    pass_no = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    run_audit(pass_no)
