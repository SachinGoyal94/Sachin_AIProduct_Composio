"""Merge knowledge parts, validate records, expose APPS.

Fail fast at import time if the dataset is malformed - this is the contract
that keeps the rest of the pipeline honest (unique ids, valid vocabularies,
absolute evidence URLs, 1-5 confidence).
"""
from __future__ import annotations

import re

from config import AUTH_METHODS, GATING, SURFACE, VERDICTS
from knowledge_a import APPS_A
from knowledge_b import APPS_B

APPS: list = APPS_A + APPS_B


def validate(records: list) -> None:
    ids = [r.id for r in records]
    assert len(ids) == len(set(ids)), "duplicate ids in knowledge base"
    assert ids == list(range(1, 101)), f"ids must be 1..100 contiguous, got {len(ids)} rows"
    for r in records:
        assert r.auth in AUTH_METHODS, f"#{r.id} {r.name}: bad auth {r.auth!r}"
        assert r.gate in GATING, f"#{r.id} {r.name}: bad gate {r.gate!r}"
        assert r.surface in SURFACE, f"#{r.id} {r.name}: bad surface {r.surface!r}"
        assert r.verdict in VERDICTS, f"#{r.id} {r.name}: bad verdict {r.verdict!r}"
        assert r.mcp in ("Yes", "No"), f"#{r.id} {r.name}: bad mcp {r.mcp!r}"
        assert 1 <= r.confidence <= 5, f"#{r.id} {r.name}: bad confidence {r.confidence}"
        assert re.match(r"^https?://", r.evidence), \
            f"#{r.id} {r.name}: evidence must be absolute URL, got {r.evidence!r}"
        assert r.does and r.breadth, f"#{r.id} {r.name}: missing does/breadth"
        if r.verdict != "Ready":
            assert r.blocker, f"#{r.id} {r.name}: non-Ready verdict needs a blocker"


validate(APPS)
