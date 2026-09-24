"""Render the single-file case-study page (index.html).

Everything on the page - every number, chart and table row - is computed
from the pipeline artifacts. The page embeds its whole dataset as JSON
(<script id="report-data">) plus a JSON-LD header, so agents can consume
it without a browser and humans get one self-explanatory scroll.

    python src/render.py
"""
from __future__ import annotations

import datetime as dt
import html
import json

from config import (AUDIT_JSON, CATEGORY_ORDER, COMPOSIO_JSON, DRAFT_CSV,
                    DRAFT_META, INDEX_HTML, OVERRIDES_CSV, PASS2_CSV,
                    PATTERNS_JSON, RESEARCH_DRAFTS, VERIFY_JSON)
from io_utils import read_csv, read_json, split_evidence

# ---------------------------------------------------------------- palette
C = {
    "oauth": "#ea580c", "apikey": "#2563eb", "basic": "#7c3aed",
    "token": "#0891b2", "hmac": "#be185d", "none": "#6b7280",
    "other": "#a16207",
    "self": "#16a34a", "paid": "#2563eb", "admin": "#d97706",
    "sales": "#dc2626", "na": "#9ca3af",
    "ready": "#16a34a", "caveat": "#d97706", "blocked": "#dc2626",
    "official": "#ea580c", "community": "#d97706", "nomcp": "#d6d3d1",
    "p1": "#f4a58a", "p2": "#16a34a",
}
AUTH_COLORS = {"OAuth2": C["oauth"], "API key": C["apikey"], "Basic": C["basic"],
               "Token": C["token"], "HMAC": C["hmac"], "None": C["none"],
               "Other": C["other"]}
GATE_COLORS = {"Open self-serve": C["self"], "Paid self-serve": C["paid"],
               "Admin approval": C["admin"],
               "Contact sales / partner": C["sales"],
               "N/A (no auth)": C["na"]}
GATE_SHORT = {"Open self-serve": "Open self-serve",
              "Paid self-serve": "Paid self-serve",
              "Admin approval": "Admin approval",
              "Contact sales / partner": "Sales / partner",
              "N/A (no auth)": "No auth"}
VERDICT_COLORS = {"Ready": C["ready"], "Ready with caveats": C["caveat"],
                  "Blocked": C["blocked"]}


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)


# ---------------------------------------------------------------- charts
def svg_donut(dist: dict, colors: dict, size: int = 210) -> str:
    total = sum(dist.values()) or 1
    r, cx, cy = 78, size / 2, size / 2
    circ = 2 * 3.14159 * r
    segs, off = [], 0.0
    for label, n in dist.items():
        frac = n / total
        dash = frac * circ
        if frac >= 0.999:
            segs.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
                        f'stroke="{colors.get(label, "#999")}" stroke-width="30"/>')
            off += dash
            continue
        segs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="{colors.get(label, "#999")}" stroke-width="30" '
            f'stroke-dasharray="{dash:.2f} {circ - dash:.2f}" '
            f'stroke-dashoffset="{-off:.2f}" transform="rotate(-90 {cx} {cy})"/>')
        off += dash
    mid = f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" class="donut-big">{total}</text>' \
          f'<text x="{cx}" y="{cy + 20}" text-anchor="middle" class="donut-sub">apps</text>'
    return (f'<svg viewBox="0 0 {size} {size}" class="donut" role="img" '
            f'aria-label="auth distribution">{"".join(segs)}{mid}</svg>')


def svg_hstack_bars(rows: list[dict], colors: dict, labels: dict,
                    unit: str = "apps") -> str:
    """rows: [{label, n, parts: {bucketname: count}}, ...]"""
    out = ['<svg viewBox="0 0 640 %d" class="bars" role="img">' % (len(rows) * 34 + 8)]
    for i, row in enumerate(rows):
        y = i * 34 + 6
        total = row["n"] or 1
        x = 210.0
        out.append(f'<text x="200" y="{y + 13}" text-anchor="end" class="bar-lab">'
                   f'{esc(row["label"])}</text>')
        for bucket, cnt in row["parts"].items():
            if not cnt:
                continue
            w = cnt / total * 415.0
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="19" '
                       f'rx="3" fill="{colors.get(bucket, "#999")}"><title>'
                       f'{esc(row["label"])} - {esc(labels.get(bucket, bucket))}: '
                       f'{cnt} {unit}</title></rect>')
            x += w
        out.append(f'<text x="632" y="{y + 13}" text-anchor="end" class="bar-val">'
                   f'{esc(row.get("pct", ""))}</text>')
    out.append("</svg>")
    return "".join(out)


def svg_ranked_bars(items: list[dict], color: str, width: int = 640) -> str:
    top = items[0]["n"] if items else 1
    out = [f'<svg viewBox="0 0 {width} {len(items) * 34 + 8}" class="bars">']
    for i, it in enumerate(items):
        y = i * 34 + 6
        w = max(6, it["n"] / max(top, 1) * 420)
        out.append(f'<text x="200" y="{y + 13}" text-anchor="end" class="bar-lab">'
                   f'{esc(it["blocker"])}</text>')
        out.append(f'<rect x="210" y="{y}" width="{w:.0f}" height="19" rx="3" '
                   f'fill="{color}"><title>{esc(it["blocker"])}: {it["n"]} apps'
                   f'</title></rect>')
        out.append(f'<text x="{214 + w:.0f}" y="{y + 13}" class="bar-val">'
                   f'{it["n"]}</text>')
    out.append("</svg>")
    return "".join(out)


def svg_accuracy_bars(aud1: dict, aud2: dict) -> str:
    groups = [("Field-level accuracy", aud1["field_accuracy"], aud2["field_accuracy"],
               f'{aud1["fields_correct"]}/{aud1["fields_scored"]} fields',
               f'{aud2["fields_correct"]}/{aud2["fields_scored"]} fields'),
              ("Full-row accuracy (all 5 fields right)", aud1["row_accuracy"],
               aud2["row_accuracy"],
               f'{aud1["rows_fully_correct"]}/{aud1["sample_size"]} apps',
               f'{aud2["rows_fully_correct"]}/{aud2["sample_size"]} apps')]
    out = ['<svg viewBox="0 0 640 205" class="bars acc-bars" role="img">']
    y = 8
    for label, v1, v2, lab1, lab2 in groups:
        out.append(f'<text x="200" y="{y + 12}" text-anchor="end" class="bar-lab">'
                   f'{esc(label)}</text>')
        for j, (v, lab, color) in enumerate(
                [(v1, lab1, C["p1"]), (v2, lab2, C["p2"])]):
            yy = y + j * 22
            w = max(8, v * 415)
            out.append(f'<rect x="210" y="{yy}" width="{w:.0f}" height="17" rx="3" '
                       f'fill="{color}"><title>{esc(label)} pass '
                       f'{1 if j == 0 else 2}: {v:.1%}</title></rect>')
            out.append(f'<text x="{216 + w:.0f}" y="{yy + 12}" class="bar-val">'
                       f'{v * 100:.0f}% <tspan class="bar-sub">({esc(lab)})</tspan>'
                       f'</text>')
        y += 60
    out.append(f'<rect x="210" y="160" width="12" height="12" rx="3" fill="{C["p1"]}"/>'
               f'<text x="228" y="170" class="legend">pass 1 - agent draft</text>'
               f'<rect x="210" y="182" width="12" height="12" rx="3" fill="{C["p2"]}"/>'
               f'<text x="228" y="192" class="legend">pass 2 - after verification loop + human</text>')
    out.append("</svg>")
    return "".join(out)


def svg_pipeline(n_flag: int, n_prop: int, n_over: int) -> str:
    """Left-to-right flow diagram with live counts."""
    def node(x, y, w, h, title, sub, fill, dark=False):
        tc = "#fff" if dark else "#1c1917"
        sc = "#fff" if dark else "#57534e"
        return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" '
                f'fill="{fill}" stroke="#e7e5e4"/>'
                f'<text x="{x + w / 2}" y="{y + h / 2 - 4}" text-anchor="middle" '
                f'class="pn" fill="{tc}">{title}</text>'
                f'<text x="{x + w / 2}" y="{y + h / 2 + 14}" text-anchor="middle" '
                f'class="ps" fill="{sc}">{sub}</text>')

    def arrow(x1, y, x2):
        return (f'<line x1="{x1}" y1="{y}" x2="{x2 - 8}" y2="{y}" '
                f'stroke="#a8a29e" stroke-width="2" marker-end="url(#arr)"/>')

    y = 54
    nodes, arrows = [], []
    xs = [4, 148, 292, 436, 580]
    w = 128
    arrows.append(arrow(132, y + 20, 148))
    nodes.append(node(xs[1], y, w, 52, "PASS 1 - draft", "LLM, memory-only", "#fde8dd", False))
    arrows.append(arrow(xs[1] + w, y + 20, xs[2]))
    nodes.append(node(xs[2], y, w, 52, "VERIFY loop", "HTTP + rules", "#e0ecff", False))
    arrows.append(arrow(xs[2] + w, y + 20, xs[3]))
    nodes.append(node(xs[3], y, w, 52, "HUMAN review", f"{n_over} corrections", "#fef3c7", False))
    arrows.append(arrow(xs[3] + w, y + 20, xs[4]))
    nodes.append(node(xs[4], y, w, 52, "PASS 2 + AUDIT", "vs ground truth", "#dcfce7", False))
    nodes.append(node(xs[0], y, w, 52, "100 apps", "10 categories", "#f5f5f4", False))
    # loop-back from verify to human via deep dive
    mid = (xs[2] + w / 2, y + 52)
    nodes.append(node(xs[2] + 6, y + 92, w - 12, 40,
                      f"DEEP-DIVE agent", f"{n_flag} flagged rows", "#ede9fe", False))
    path = (f'<path d="M {mid[0]} {mid[1]} C {mid[0]} {y + 78}, {mid[0]} {y + 78}, '
            f'{mid[0]} {y + 92}" fill="none" stroke="#a8a29e" stroke-width="2"/>')
    back = (f'<path d="M {xs[2] + w / 2} {y + 92} C {xs[2] + w / 2} {y + 72}, '
            f'{xs[3] + w / 2} {y + 86}, {xs[3] + w / 2} {y + 52}" fill="none" '
            f'stroke="#a8a29e" stroke-width="2" stroke-dasharray="4 3"/>')
    legend = (f'<text x="4" y="{y + 148}" class="legend">{n_prop} deep-dive '
              f'proposals were drafted; a human promoted {n_over} corrections'
              f'</text>'
              f'<text x="4" y="{y + 168}" class="legend">into the final dataset. '
              f'Pass 2 is re-verified and audited independently.</text>')
    return ('<svg viewBox="0 0 712 232" class="pipe" role="img" aria-label="pipeline">'
            '<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="7" '
            'refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#a8a29e"/>'
            "</marker></defs>" + "".join(nodes) + "".join(arrows) + path + back +
            legend + "</svg>")
