"""Thin Gemini REST client shared by the draft and deep-dive stages.

Uses only `requests` (no SDK) so the pipeline runs anywhere. Calls are
cached on disk so re-runs are reproducible and cheap.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import requests

from config import GEMINI_MODEL, GEMINI_RETRIES, GEMINI_TIMEOUT, OUT

_CACHE = OUT / "llm_cache"
_API = "https://generativelanguage.googleapis.com/v1beta/models"


def _key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or None


def available() -> bool:
    return bool(_key())


def call(prompt: str, system: str = "", model: str = GEMINI_MODEL,
         temperature: float = 0.2, use_cache: bool = True) -> str:
    """One generateContent call, memoized by (model, system, prompt)."""
    k = _key()
    if not k:
        raise RuntimeError("GEMINI_API_KEY missing")
    _CACHE.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(f"{model}|{temperature}|{system}|{prompt}".encode()).hexdigest()[:20]
    cache_file = _CACHE / f"{h}.json"
    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))["text"]

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature,
                             "responseMimeType": "application/json"},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    last = None
    for attempt in range(GEMINI_RETRIES + 1):
        try:
            r = requests.post(f"{_API}/{model}:generateContent", params={"key": k},
                              json=body, timeout=GEMINI_TIMEOUT)
            if r.status_code == 429 or r.status_code >= 500:
                wait = 2 ** attempt * 5
                time.sleep(wait)
                last = f"HTTP {r.status_code}"
                continue
            r.raise_for_status()
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            if use_cache:
                cache_file.write_text(json.dumps({"text": text}, ensure_ascii=False),
                                      encoding="utf-8")
            return text
        except Exception as e:  # noqa: BLE001 - retry, then surface
            last = f"{type(e).__name__}: {e}"[:300]
            time.sleep(2 ** attempt * 3)
    raise RuntimeError(f"gemini call failed after retries: {last}")


def parse_json(text: str):
    """Parse model output that should be JSON (strips fences if any)."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    return json.loads(t)
