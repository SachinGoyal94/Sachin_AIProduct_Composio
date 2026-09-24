"""Load/save helpers shared by pipeline stages."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from config import DATA, OUT, AppRecord
from knowledge import APPS, validate


def load_records() -> list[AppRecord]:
    """Current knowledge base (Pass-1 or Pass-2 after overrides are applied)."""
    return APPS


def apply_overrides(records: list[AppRecord], path: Path | None = None) -> tuple[list[AppRecord], int]:
    """Apply human/live-pass corrections from overrides.csv onto the records.

    CSV columns: id,field,value,note  (field in auth|gate|surface|mcp|verdict|
    blocker|evidence|breadth|does|confidence|notes). Multiple rows per app are
    allowed; applied in file order. Returns (new list, number of overrides).
    """
    path = path or (DATA / "overrides.csv")
    if not path.exists():
        return records, 0
    by_id = {r.id: r for r in records}
    out = {rid: rec.__class__(**dict(rec.__dict__)) for rid, rec in by_id.items()}
    n = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rid = int(row["id"])
            fld, val = row["field"].strip(), row["value"].strip()
            rec = out[rid]
            if fld == "confidence":
                val = int(val)
            if not hasattr(rec, fld):
                raise ValueError(f"unknown field {fld!r} for app {rid}")
            setattr(rec, fld, val)
            if row.get("note") and row["note"] not in rec.notes:
                rec.notes = (rec.notes + " | " + row["note"]).strip(" |")
            n += 1
    corrected = list(out.values())
    validate(corrected)  # overrides are data too - re-check the contract
    return corrected, n


def save_json(obj, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def save_csv(rows: list[dict], name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    if not rows:
        p.write_text("", encoding="utf-8")
        return p
    fields = list(rows[0].keys())
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return p
