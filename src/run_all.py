"""One-command orchestrator: rebuilds every artifact and the case-study page.

    python src/run_all.py            # full pipeline (network required)
    python src/run_all.py --skip-net # skip live stages (offline demo)

Stages:
  1. analyze.py 1      -> out/apps_pass1.csv, pass1 flags (pristine knowledge core)
  2. verify.py 1       -> out/verification_pass1.json (live HTTP loop)
  3. research.py       -> data/research_drafts.csv (agent search->fetch->extract->draft;
                          drafts are proposals, human promotes them to overrides.csv)
  4. analyze.py 2      -> out/apps_pass2.csv (after data/overrides.csv corrections)
  5. verify.py 2       -> out/verification_pass2.json (live HTTP loop, corrected data)
  6. composio_check.py -> out/composio_toolbelt.json (optional; needs COMPOSIO_API_KEY)
  7. patterns.py       -> out/patterns.json (clusters, distributions, flips)
  8. audit.py 1|2      -> out/audit_pass*.json (ground-truth accuracy per pass)
  9. render.py         -> index.html (this repo root)
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent
PY = sys.executable


def run(stage: list[str], allow_fail: bool = False) -> bool:
    print(f"\n=== {' '.join(stage)} ===", flush=True)
    t0 = time.time()
    r = subprocess.run([PY, *stage], cwd=SRC)
    dt = time.time() - t0
    ok = r.returncode == 0
    print(f"--- {'OK' if ok else 'FAILED'} in {dt:.1f}s ---", flush=True)
    if not ok and not allow_fail:
        sys.exit(r.returncode)
    return ok


def main() -> None:
    skip_net = "--skip-net" in sys.argv
    t0 = time.time()

    run(["analyze.py", "1"])
    if not skip_net:
        run(["verify.py", "1"], allow_fail=True)
        run(["research.py"], allow_fail=True)  # drafts a human later promotes
    run(["analyze.py", "2"])
    if not skip_net:
        run(["verify.py", "2"], allow_fail=True)
        run(["composio_check.py"], allow_fail=True)  # optional by design
    run(["patterns.py"])
    run(["audit.py", "1"])
    run(["audit.py", "2"])
    run(["render.py"])

    print(f"\nAll done in {time.time() - t0:.1f}s -> index.html + out/*.json + out/*.csv")


if __name__ == "__main__":
    main()
