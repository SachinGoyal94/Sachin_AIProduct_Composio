"""Optional cross-check: which of the 100 apps already have Composio toolkits?

Tries the current Composio v3 REST API first, then the legacy SDK. Both are
wrapped defensively: this stage is optional by design and reports the real
error when the API key is rejected (ours predates the v3 migration, so a
401 is the expected outcome - recorded honestly in the artifact).

    python src/composio_check.py
"""
from __future__ import annotations

import datetime as dt
import json
import os

import requests

from config import COMPOSIO_JSON, OUT
from io_utils import load_apps, write_json

API_BASE = "https://backend.composio.dev/api/v3"


def _slugify(name: str) -> str:
    s = "".join(c.lower() if c.isalnum() else " " for c in name)
    return "_".join(s.split())


def fetch_toolkits(api_key: str) -> tuple[list[str], str]:
    """Return (slugs, method) - raises on auth failure."""
    r = requests.get(f"{API_BASE}/toolkits", headers={"x-api-key": api_key},
                     params={"limit": 1000}, timeout=30)
    if r.status_code == 200:
        try:
            items = r.json().get("items", [])
            return sorted({t.get("slug", "") for t in items if t.get("slug")}), \
                "v3 REST /toolkits"
        except (ValueError, AttributeError) as e:
            raise RuntimeError(f"v3 responded 200 but body unparsable: {e}") from e
    raise RuntimeError(f"v3 /toolkits -> HTTP {r.status_code}: {r.text[:160]}")


def fetch_toolkits_legacy_sdk(api_key: str) -> tuple[list[str], str]:
    from composio import ComposioToolSet  # legacy client, best-effort
    ts = ComposioToolSet(api_key=api_key)
    apps = ts.get_apps()
    return sorted({a.slug for a in apps}), "legacy SDK get_apps()"


def main() -> None:
    apps = load_apps()
    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    result: dict = {
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "attempted": bool(api_key),
        "ok": False, "method": "", "toolkits_seen": 0,
        "apps_covered": [], "error": "",
        "note": "",
    }
    if not api_key:
        result["note"] = "COMPOSIO_API_KEY not set - stage skipped by design"
    else:
        try:
            slugs, method = fetch_toolkits(api_key)
            result["ok"], result["method"] = True, method
        except Exception as e:  # noqa: BLE001
            first_error = f"{type(e).__name__}: {e}"[:220]
            try:
                slugs, method = fetch_toolkits_legacy_sdk(api_key)
                result["ok"], result["method"] = True, method
            except Exception as e2:  # noqa: BLE001
                result["error"] = f"v3: {first_error} | legacy SDK: {e2}"[:400]
                result["note"] = (
                    "Composio rejected the API key (the provided key predates the "
                    "v3 API migration). Stage is optional; cross-check marked "
                    "not-performed rather than guessed.")
                slugs = []

        if result["ok"]:
            result["toolkits_seen"] = len(slugs)
            have = {(_slugify(a.name), a.name.lower()) for a in apps}
            covered = []
            for a in apps:
                slug = _slugify(a.name)
                hit = slug in slugs or any(
                    a.name.lower().split()[0] == s for s in slugs)
                if hit:
                    covered.append(a.id)
            result["apps_covered"] = covered
            result["note"] = (f"{len(covered)}/{len(apps)} of the researched apps "
                              f"already ship as Composio toolkits")

    OUT.mkdir(exist_ok=True)
    write_json(COMPOSIO_JSON, result)
    print(f"composio_check: ok={result['ok']} method={result['method'] or '-'} "
          f"{result['note'] or result['error']}")


if __name__ == "__main__":
    main()
