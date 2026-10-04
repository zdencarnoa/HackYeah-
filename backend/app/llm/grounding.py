"""Reject LLM text that adds facts the evidence does not contain.

Cheap, deterministic checks: every domain, URL, e-mail address and number in the
answer must already appear in the input. A rejected answer is replaced by the
template, so a hallucination never reaches the user.
"""
from __future__ import annotations

import re

DOMAIN = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.I)
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
PLACEHOLDER = re.compile(r"\{(?:name|messages|recipients|departments|employee)\}")


def _tokens(text: str) -> set[str]:
    text = PLACEHOLDER.sub(" ", text)
    return {m.lower() for m in DOMAIN.findall(text)} | set(NUMBER.findall(text))


def grounded(answer_texts: list[str], source_texts: list[str]) -> bool:
    allowed = set().union(*(_tokens(t) for t in source_texts)) if source_texts else set()
    # Step numbers in a numbered list ("1.", "2.") are formatting, not facts.
    allowed |= {str(i) for i in range(1, 10)}
    return all(_tokens(t) <= allowed for t in answer_texts)


def short_strings(value, max_items: int, max_len: int) -> list[str] | None:
    if not isinstance(value, list) or len(value) > max_items:
        return None
    if not all(isinstance(v, str) and 0 < len(v.strip()) <= max_len for v in value):
        return None
    return [v.strip() for v in value]
