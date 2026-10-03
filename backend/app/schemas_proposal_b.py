"""PROPOSED contracts for Person B's part (risk fusion + explanations).

Merge into backend/app/schemas.py together with the team (do not edit schemas.py
alone). `Severity` is identical to Person C's proposal on branch `tojke`
(app/schemas_proposal.py), so B's verdict and C's incidents use one scale;
keep a single copy when merging.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import IntEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import Signal


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Severity(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


class Explanation(BaseModel):
    summary: str  # one plain-language sentence: the verdict
    reasons: list[str]  # plain-language evidence, strongest first (from Signal.evidence)
    source: Literal["llm", "template"]  # template = deterministic fallback, no network needed


class Assessment(BaseModel):
    message_id: str
    risk: Severity  # set only by risk fusion, never by the LLM
    score: int  # fusion points behind the risk level, for "Advanced details"
    signals: list[Signal]  # A's signals plus B's ml_phishing signal, strongest first
    ml_confidence: float | None = None  # calibrated phishing probability 0-1; None if the model was unavailable
    ml_model: str | None = None  # "distilbert-v1" or "tfidf-fallback"
    uncertainties: list[str] = Field(default_factory=list)  # what could not be checked; never counted as evidence
    explanation: Explanation
    recommended_action: str  # every result ends with a next action
    assessed_at: datetime = Field(default_factory=_now)
