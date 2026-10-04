"""PROPOSED contracts for Person C's part.

Merge into backend/app/schemas.py at the Hour-0 meeting (do not edit schemas.py
alone). Additions beyond the plan are marked  # NEW  and need team sign-off.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import IntEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return uuid4().hex[:12]


class Severity(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


EvidenceKind = Literal[
    "email_scored", "link_clicked", "password_reuse", "unusual_signin", "user_report"
]
InteractionKind = Literal["none", "clicked", "downloaded", "password", "other_info"]


class Evidence(BaseModel):
    id: str = Field(default_factory=_id)
    kind: EvidenceKind
    employee_id: str
    message_id: str | None = None
    domain: str | None = None
    source: Literal["automatic", "reported"] = "automatic"
    timestamp: datetime = Field(default_factory=_now)
    interaction_kind: InteractionKind | None = None  # NEW: only for user_report
    risk: Severity | None = None  # NEW: only for email_scored


class TimelineItem(BaseModel):
    timestamp: datetime
    employee_id: str
    text: str  # plain language
    source: Literal["automatic", "reported"]  # UI shows Automatic / Reported tag


class ChecklistItem(BaseModel):
    id: str  # NEW
    key: str  # NEW: stable name, e.g. "revoke_sessions"
    action: str
    rationale: str
    area: Literal["account", "messages", "notifications", "investigation"]  # NEW: D's recovery areas
    done: bool = False
    needs_approval: bool = False  # NEW: containment items wait for the admin
    containment_kind: str | None = None  # NEW: D's action name, e.g. "quarantine"
    approved_by: str | None = None  # NEW
    approved_at: datetime | None = None  # NEW
    done_at: datetime | None = None  # NEW


class Incident(BaseModel):
    id: str
    type: str
    severity: Severity
    campaign_id: str | None = None
    affected_employees: list[str]
    evidence: list[Evidence]
    checklist: list[ChecklistItem] = []
    timeline: list[TimelineItem]
    created_at: datetime


class Interaction(BaseModel):
    message_id: str
    employee_id: str
    kind: InteractionKind


class InteractionResult(BaseModel):
    guidance: list[str]
    already_detected: list[str]  # e.g. ["link_clicked", "password_reuse"]
    incident: Incident | None = None


class PasswordReuseEvent(BaseModel):
    """Chrome PASSWORD_REUSE_EVENT-shaped payload. Never carries a real password."""

    user: str  # employee email
    url: str
    domain: str
    reused_credential: str = "work_account"  # label only, never stored
    timestamp: datetime = Field(default_factory=_now)


class PubSubMessage(BaseModel):
    data: str  # base64(JSON PasswordReuseEvent)
    messageId: str | None = None
    attributes: dict[str, str] = {}


class PubSubPush(BaseModel):
    message: PubSubMessage
    subscription: str | None = None


class MessageIn(BaseModel):  # NEW: A's Message fields C needs, plus B's risk level
    id: str
    sender: str
    recipient: str  # employee email (or id)
    subject: str
    body: str
    urls: list[str] = []  # original URLs, before link rewriting
    received_at: datetime = Field(default_factory=_now)
    risk: Severity  # from B's Assessment


class Campaign(BaseModel):
    id: str
    name: str
    message_ids: list[str]
    recipients: list[str]
    departments: list[str]
    shared_traits: list[str]  # plain-language observations, see campaigns/matching.py
    incident_id: str | None = None  # NEW: lets the UI jump from campaign to incident
    updated_at: datetime


class ApproveBody(BaseModel):  # NEW
    approved_by: str = "admin"


class CompleteBody(BaseModel):  # NEW
    done: bool = True  # False re-opens a step


class AreaProgress(BaseModel):  # NEW
    done: int
    total: int
    percent: int


class RecoveryProgress(BaseModel):  # NEW: payload of the recovery.updated event
    incident_id: str
    percent: int
    areas: dict[str, AreaProgress]
    remaining: list[str]  # actions still open, in checklist order


class TextResult(BaseModel):  # NEW
    text: str
    source: Literal["template", "llm"]


class Dashboard(BaseModel):  # NEW: overview tiles
    open_incidents: int
    by_severity: dict[str, int]
    active_campaigns: int
    affected_employees: int
    pending_approvals: int
    checklist_done: int
    checklist_total: int
    latest_critical_incident_id: str | None = None
