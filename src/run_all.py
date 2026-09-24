"""One-command orchestrator: rebuilds every artifact and the case-study page.

    python src/run_all.py              # full pipeline (network + Gemini key)
    python src/run_all.py --offline    # reuse committed artifacts, no network

Stages
  1. agent_draft.py   pass 1 - memory-only draft of all 100 apps (LLM, cached)
  2. verify.py 1      live evidence checks + rule engine over pass 1
  3. research.py      deep-dive flagged rows -> data/research_drafts.csv
                      (proposals only; a HUMAN promotes them to overrides)
  4. apply.py         draft + data/overrides.csv -> pass 2 dataset
  5. verify.py 2      live evidence checks + rule engine over pass 2
  6. composio_check.py  optional Composio toolbelt cross-reference
  7. patterns.py      distributions, clusters, headline insights
  8. audit.py 1|2     strict ground-truth scoring of pass 1 and pass 2
  9. render.py        index.html (single-file case study)
 10. report.py        out/research_report.json (machine-readable mirror)
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent
PY = sys.executable

STAGES = [
    (["agent_draft.py"], "pass 1: memory-only draft (LLM)"),
    (["verify.py", "1"], "verify pass 1 (live HTTP + rules)"),
    (["research.py"], "deep-dive flagged rows -> proposals"),
    (["apply.py"], "apply human-promoted overrides -> pass 2"),
    (["verify.py", "2"], "verify pass 2 (live HTTP + rules)"),
    (["composio_check.py"], "composio toolbelt cross-check (optional)"),
    (["patterns.py"], "pattern mining"),
    (["audit.py", "1"], "audit pass 1 vs ground truth"),
    (["audit.py", "2"], "audit pass 2 vs ground truth"),
    (["render.py"], "render index.html"),
    (["report.py"], "machine-readable report JSON"),
]

OFFLINE = [
    (["apply.py"], "apply overrides -> pass 2"),
    (["patterns.py"], "pattern mining"),
    (["audit.py", "1"], "audit pass 1 vs ground truth"),
    (["audit.py", "2"], "audit pass 2 vs ground truth"),
    (["render.py"], "render index.html"),
    (["report.py"], "machine-readable report JSON"),
]


def run(stage: list[str], allow_fail: bool = False) -> bool:
    print(f"\n=== {' '.join(stage)} ===", flush=True)
    t0 = time.time()
    r = subprocess.run([PY, *stage], cwd=SRC)
    print(f"--- {'OK' if r.returncode == 0 else 'FAILED'} "
          f"in {time.time() - t0:.1f}s ---", flush=True)
    if r.returncode != 0 and not allow_fail:
        sys.exit(r.returncode)
    return r.returncode == 0


def main() -> None:
    offline = "--offline" in sys.argv
    t0 = time.time()
    plan = OFFLINE if offline else STAGES
    print(f"research pipeline - {'OFFLINE (committed artifacts)' if offline else 'FULL'} "
          f"run, {len(plan)} stages")
    for stage, _ in plan:
        allow = any(s in stage[0] for s in ("composio_check.py", "research.py"))
        run(stage, allow_fail=allow)
    print(f"\nDone in {time.time() - t0:.1f}s -> index.html + out/* + data/*")


if __name__ == "__main__":
    main()
