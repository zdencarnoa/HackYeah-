"""Where LLM answers come from, in order (every caller falls back to templates after):

1. cache   app/llm/cache/responses.json, generated before the demo (no network needed)
2. server  Qwen2.5-14B on the GPU box via SSH tunnel (app/llm/serve_openai.py), ~5 s
           LLM_SERVER_URL, default http://localhost:8001/v1
3. local   Ollama on this laptop, qwen2.5:3b, ~25 s on a laptop CPU
           LLM_LOCAL_URL, default http://localhost:11434/v1; LLM_LOCAL_MODEL
An endpoint that is not running refuses the connection at once, so a missing tunnel
or Ollama costs nothing. LLM_LIVE=0 switches live calls off (cache + templates only).
"""
from __future__ import annotations

import json
import logging
import os
from functools import cache
from pathlib import Path

import httpx

from app.llm.prompts import fingerprint

log = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).resolve().parent / "cache" / "responses.json"


def endpoints() -> list[tuple[str, str, str, float]]:
    """(name, base URL, model, timeout in s), best first."""
    if os.environ.get("LLM_LIVE", "1") == "0":
        return []
    return [
        ("server", os.environ.get("LLM_SERVER_URL", "http://localhost:8001/v1"), "qwen2.5-14b",
         float(os.environ.get("LLM_SERVER_TIMEOUT", "20"))),
        ("local", os.environ.get("LLM_LOCAL_URL", "http://localhost:11434/v1"),
         os.environ.get("LLM_LOCAL_MODEL", "qwen2.5:3b"), float(os.environ.get("LLM_LOCAL_TIMEOUT", "90"))),
    ]


@cache
def _cached() -> dict[str, dict]:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def parse_json(text: str) -> dict | None:
    """The model's JSON answer, tolerating code fences and text around it."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _call(base: str, model: str, timeout: float, messages: list[dict]) -> dict | None:
    try:
        response = httpx.post(f"{base.rstrip('/')}/chat/completions", timeout=httpx.Timeout(timeout, connect=2.0),
                              json={"model": model, "messages": messages, "temperature": 0,
                                    "response_format": {"type": "json_object"}})
        response.raise_for_status()
        return parse_json(response.json()["choices"][0]["message"]["content"])
    except Exception as exc:  # not running, slow or malformed: try the next source
        log.info("LLM endpoint %s unavailable: %s", base, exc)
        return None


def ask(messages: list[dict], live: bool = True, allow_local: bool = True) -> tuple[dict | None, str | None]:
    """(answer, origin) where origin is "cache", "server" or "local"; (None, None) when none answers.
    live=False never waits on a model: cache only (for scan-on-delivery).
    allow_local=False skips the slow laptop model (for calls a person waits on, e.g. C's incident pages)."""
    if (hit := _cached().get(fingerprint(messages))) is not None:
        return hit, "cache"
    for name, base, model, timeout in endpoints() if live else []:
        if name == "local" and not allow_local:
            continue
        if (answer := _call(base, model, timeout, messages)) is not None:
            return answer, name
    return None, None
