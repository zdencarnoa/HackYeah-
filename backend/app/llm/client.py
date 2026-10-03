"""Where LLM answers come from, in order: the offline cache, a live model, nothing.

Cache: app/llm/cache/responses.json, generated before the demo by app.llm.batch
(an open-source model on the GPU server), so the demo needs no network.

Live (optional): any OpenAI-compatible chat endpoint, e.g. Ollama on the
presenting laptop or an SSH tunnel to the GPU server:
    LLM_BASE_URL=http://localhost:11434/v1  LLM_MODEL=qwen2.5:3b
Unset = no live calls. Every caller falls back to templates when this returns None.
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
TIMEOUT_S = float(os.environ.get("LLM_TIMEOUT", "8"))


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


def _live(messages: list[dict]) -> dict | None:
    base = os.environ.get("LLM_BASE_URL")
    if not base:
        return None
    try:
        response = httpx.post(f"{base.rstrip('/')}/chat/completions", timeout=TIMEOUT_S, json={
            "model": os.environ.get("LLM_MODEL", "qwen2.5:3b"), "messages": messages,
            "temperature": 0.2, "response_format": {"type": "json_object"}})
        response.raise_for_status()
        return parse_json(response.json()["choices"][0]["message"]["content"])
    except Exception as exc:  # slow, offline or malformed: the template takes over
        log.warning("live LLM unavailable: %s", exc)
        return None


def ask(messages: list[dict]) -> tuple[dict | None, str | None]:
    """(answer, origin) where origin is "cache" or "live"; (None, None) when neither has one."""
    if (hit := _cached().get(fingerprint(messages))) is not None:
        return hit, "cache"
    if (answer := _live(messages)) is not None:
        return answer, "live"
    return None, None
