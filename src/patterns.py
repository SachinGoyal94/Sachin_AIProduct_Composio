"""Pattern clustering: aggregates the final dataset into the headline findings.

Everything the case-study page states numerically is computed here, so the
page and the data can never drift apart. Output: out/patterns.json
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from config import OUT
from io_utils import apply_overrides, load_records, save_json

BLOCKER_THEMES = [
    ("App review / approval", [r"app review", r"review process", r"approv", r"vetting",
                               r"verification", r"waitlist", r"developer token approval"]),
    ("Partnership / contact-sales", [r"partner", r"contact sales", r"sales-led", r"partnership",
                                     r"onboarding", r"provisioned by", r"csm", r"invite",
                                     r"login wall"]),
    ("Paid plan required", [r"paid", r"plan", r"pricing", r"tier", r"credits", r"acu-based",
                            r"pay-as-you-go", r"bundle", r"enterprise"]),
    ("Admin / instance needed", [r"admin", r"instance", r"self-host", r"workspace"]),
    ("Thin API surface / docs", [r"small api", r"tiny api", r"narrow", r"sparse", r"cli only",
                                 r"cli-first", r"not an api", r"docs-gat", r"thin",
                                 r"sql-over-rest", r"aging"]),
]


def cluster_blockers(records) -> list[dict]:
    """Cluster blocker text for non-Ready apps only.

    Ready apps may still carry a 'blocker' column value (it reads as a caveat
    in the table), but caveats are not blockers and must not pollute the
    'most common blocker' analysis.
    """
    counts = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for r in records:
        if not r.blocker or r.verdict == "Ready":
            continue
        b = r.blocker.lower()
        for theme, pats in BLOCKER_THEMES:
            if any(re.search(p, b) for p in pats):
                counts[theme] += 1
                if len(examples[theme]) < 4:
                    examples[theme].append(f"{r.name}: {r.blocker}")
                break
        else:
            counts["Other"] += 1
            if len(examples["Other"]) < 4:
                examples["Other"].append(f"{r.name}: {r.blocker}")
    return [{"theme": t, "count": c, "examples": examples[t]}
            for t, c in counts.most_common()]


def dist(records, attr: str) -> list[dict]:
    c = Counter(getattr(r, attr) for r in records)
    total = len(records)
    return [{"value": k, "count": c, "pct": round(100 * c / total, 1)}
            for k, c in c.most_common()]


def cross(records, attr1: str, attr2: str) -> dict:
    tab: dict[str, Counter] = defaultdict(Counter)
    for r in records:
        v1, v2 = getattr(r, attr1), getattr(r, attr2)
        # allow method names like 'canonical_category'
        v1 = v1() if callable(v1) else v1
        v2 = v2() if callable(v2) else v2
        tab[v1][v2] += 1
    return {k: dict(v) for k, v in tab.items()}


def run() -> dict:
    records, n_ovr = apply_overrides(load_records())
    pass1 = load_records()  # pristine core for flips

    # verdict flips between passes
    flips = []
    p1 = {r.id: r for r in pass1}
    for r in records:
        if p1[r.id].verdict != r.verdict:
            flips.append({"id": r.id, "name": r.name,
                          "from": p1[r.id].verdict, "to": r.verdict})

    easy_wins = sorted(
        (r for r in records if r.verdict == "Ready" and r.gate.startswith("Self-serve")
         and r.mcp == "Yes"),
        key=lambda r: r.canonical_category())

    outreach = sorted(
        (r for r in records if r.verdict == "Blocked"
         or (r.verdict == "Ready with caveats" and r.gate == "Gated")),
        key=lambda r: r.canonical_category())

    mcp_by_cat = cross(records, "canonical_category", "mcp")

    patterns = {
        "n_apps": len(records),
        "n_overrides_applied": n_ovr,
        "auth_dist": dist(records, "auth"),
        "gate_dist": dist(records, "gate"),
        "verdict_dist": dist(records, "verdict"),
        "mcp_dist": dist(records, "mcp"),
        "surface_dist": dist(records, "surface"),
        "auth_by_gate": cross(records, "auth", "gate"),
        "gate_by_category": cross(records, "canonical_category", "gate"),
        "mcp_by_category": mcp_by_cat,
        "blocker_themes": cluster_blockers(records),
        "verdict_flips": flips,
        "n_flips": len(flips),
        "easy_wins": [{"id": r.id, "name": r.name, "category": r.canonical_category(),
                       "auth": r.auth} for r in easy_wins],
        "needs_outreach": [{"id": r.id, "name": r.name, "category": r.canonical_category(),
                            "blocker": r.blocker} for r in outreach],
    }
    save_json(patterns, "patterns.json")

    # headline printout
    a = patterns["auth_dist"][0]
    g = patterns["gate_dist"][0]
    v = next(x for x in patterns["verdict_dist"] if x["value"] == "Ready")
    print(f"auth winner: {a['value']} {a['pct']}% | gate winner: {g['value']} {g['pct']}%")
    print(f"Ready: {v['count']}% | MCP available: "
          f"{next(x['pct'] for x in patterns['mcp_dist'] if x['value'] == 'Yes')}%")
    print(f"verdict flips pass1->pass2: {len(flips)}")
    for f in flips:
        print(f"  #{f['id']:3d} {f['name']}: {f['from']} -> {f['to']}")
    print("blocker themes:", [(t['theme'], t['count']) for t in patterns['blocker_themes']])
    return patterns


if __name__ == "__main__":
    run()
