"""Typed record + CSV/JSON helpers shared by every stage."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from config import (
    APPS_CSV, AUDIT_CSV, OVERRIDES_CSV, RESEARCH_DRAFTS, VERIFIED_CSV,
    AUTH_METHODS, GATING, MCP, SCORED_FIELDS, SURFACE, VERDICTS,
)


@dataclass
class App:
    id: int
    name: str
    category: str
    website: str
    does: str = ""
    auth: str = ""
    auth_detail: str = ""
    gate: str = ""
    gate_detail: str = ""
    surface: str = ""
    breadth: str = ""
    mcp: str = ""
    mcp_evidence: str = ""
    verdict: str = ""
    blocker: str = ""
    evidence: str = ""          # primary docs URL (comma-joined if several)
    confidence: int = 3         # 1-5, set by review
    notes: str = ""

    @classmethod
    def fieldnames(cls) -> list[str]:
        return [f.name for f in fields(cls)]


def _coerce(r: dict) -> dict:
    """CSV gives strings; coerce the typed fields."""
    r = dict(r)
    try:
        r["id"] = int(r["id"])
    except (KeyError, ValueError):
        pass
    try:
        r["confidence"] = int(r["confidence"])
    except (KeyError, ValueError, TypeError):
        r["confidence"] = 3
    return r


def load_apps() -> list[App]:
    apps = [App(**_coerce(r)) for r in read_csv(APPS_CSV)]
    apps.sort(key=lambda a: a.id)
    return apps


def load_verified() -> list[App]:
    return [App(**_coerce(r)) for r in read_csv(VERIFIED_CSV)]


def load_overrides() -> list[dict]:
    return read_csv(OVERRIDES_CSV)


def load_research_drafts() -> list[dict]:
    return read_csv(RESEARCH_DRAFTS)


def load_audit_sample() -> list[dict]:
    return read_csv(AUDIT_CSV)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        seen: dict[str, None] = {}
        for r in rows:
            seen.update({k: None for k in r})
        fieldnames = list(seen)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def read_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def apps_to_rows(apps: list[App]) -> list[dict]:
    return [asdict(a) for a in apps]


def normalize(value: str | None) -> str:
    """Loose normalization so audits compare values, not punctuation."""
    v = (value or "").strip().lower()
    return " ".join(v.split())


def check_vocabulary(app: App) -> list[str]:
    """Return a list of vocabulary violations for one row (empty = clean)."""
    bad = []
    if app.auth not in AUTH_METHODS:
        bad.append(f"auth={app.auth!r}")
    if app.gate not in GATING:
        bad.append(f"gate={app.gate!r}")
    if app.surface not in SURFACE:
        bad.append(f"surface={app.surface!r}")
    if app.mcp not in MCP:
        bad.append(f"mcp={app.mcp!r}")
    if app.verdict not in VERDICTS:
        bad.append(f"verdict={app.verdict!r}")
    if app.verdict == "Blocked" and not app.blocker:
        bad.append("Blocked verdict without blocker")
    return bad


def split_evidence(app_or_str) -> list[str]:
    raw = app_or_str if isinstance(app_or_str, str) else app_or_str.get("evidence", "")
    return [u.strip() for u in (raw or "").split(",") if u.strip()]
