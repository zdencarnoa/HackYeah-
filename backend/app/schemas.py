"""Shared contracts between backend areas and the frontend.

DRAFT. Only the simulation section (Person D) is filled in so far. Other areas
add their sections here, and changes to existing models are agreed with the team
because the frontend mocks are built against this file.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Simulation (Person D): synthetic organization, demo mail, simulated events,
# blast radius, containment and recovery. Everything here is simulated.
# ---------------------------------------------------------------------------


class Department(StrEnum):
    FINANCE = "Finance"
    SALES = "Sales"
    OPERATIONS = "Operations"
    HR = "HR"
    IT = "IT"
    EXECUTIVE = "Executive"


class Employee(BaseModel):
    id: str  # "e01"
    name: str
    email: str
    department: Department
    title: str
    manager_id: str | None = None
    is_admin: bool = False
    # Service ids this employee can reach through the identity provider.
    access: list[str] = Field(default_factory=list)


class ServiceKind(StrEnum):
    IDENTITY_PROVIDER = "identity_provider"
    EMAIL = "email"
    FILE_STORAGE = "file_storage"
    INTERNAL_APP = "internal_app"
    DATA = "data"  # a sensitive data store sitting behind an app


Sensitivity = Literal["low", "medium", "high"]


class Service(BaseModel):
    id: str  # "idp", "mail", "erp", ...
    name: str
    kind: ServiceKind
    sensitivity: Sensitivity
    description: str


class Dependency(BaseModel):
    """Directed edge in the org graph: compromising `source` exposes `target`."""

    source: str  # service id
    target: str  # service id
    relation: str  # "signs in to", "stores", ...


class Organization(BaseModel):
    name: str
    domain: str
    employees: list[Employee]
    services: list[Service]
    dependencies: list[Dependency]


class ApprovedLogin(BaseModel):
    """A domain where typing an organization password is expected and safe."""

    domain: str
    service_id: str
    description: str


AuthResult = Literal["pass", "fail", "softfail", "none"]


class AuthResults(BaseModel):
    spf: AuthResult
    dkim: AuthResult
    dmarc: AuthResult


class Attachment(BaseModel):
    filename: str
    content_type: str
    size_bytes: int


class ScenarioLabel(BaseModel):
    """Ground truth for evaluation and demo checks.

    Analyzers, scoring and the LLM must never read this. It is stripped before
    a message is handed to ingestion.
    """

    label: Literal["phishing", "legitimate"]
    category: str  # "credential_theft", "invoice", "meeting", ...
    campaign_id: str | None = None


class SimEmail(BaseModel):
    """A demo message as stored in data/emails/ before delivery."""

    id: str
    sender_name: str
    sender_address: str
    reply_to: str | None = None
    to: list[str]
    cc: list[str] = Field(default_factory=list)
    subject: str
    body_text: str
    urls: list[str] = Field(default_factory=list)  # as they appear in the body
    attachments: list[Attachment] = Field(default_factory=list)
    auth: AuthResults
    sending_ip: str
    # Seconds after demo start when the attack engine delivers this message.
    deliver_offset_s: int
    scenario: ScenarioLabel


class SimEventType(StrEnum):
    EMAIL_DELIVERED = "email_delivered"
    LINK_CLICKED = "link_clicked"
    PASSWORD_REUSE = "password_reuse"  # mirrors Chrome PASSWORD_REUSE_EVENT
    UNUSUAL_SIGN_IN = "unusual_sign_in"
    CONTAINMENT_ACTION = "containment_action"
    DEMO_RESET = "demo_reset"


class SimEvent(BaseModel):
    id: str
    type: SimEventType
    at: datetime
    employee_id: str | None = None
    message_id: str | None = None
    # Type-specific fields, e.g. {"domain": "login.micr0soft-example.com"} for
    # PASSWORD_REUSE or {"country": "..", "ip": ".."} for UNUSUAL_SIGN_IN.
    # Passwords are never stored or sent, only the fact that one was entered.
    data: dict[str, str | int | bool] = Field(default_factory=dict)
    simulated: Literal[True] = True


BlastNodeKind = Literal["employee", "identity_provider", "service", "data", "people"]


class BlastRadiusNode(BaseModel):
    id: str
    label: str
    kind: BlastNodeKind
    sensitivity: Sensitivity | None = None
    at_risk: bool


class BlastRadiusEdge(BaseModel):
    source: str
    target: str
    relation: str


class BlastRadius(BaseModel):
    """Graph of what a compromised account could reach. Shaped for React Flow."""

    employee_id: str
    nodes: list[BlastRadiusNode]
    edges: list[BlastRadiusEdge]
    affected_service_ids: list[str]
    explanation: str  # plain language, states uncertainty
    simulated: Literal[True] = True


class ContainmentActionType(StrEnum):
    QUARANTINE_MESSAGES = "quarantine_messages"
    BLOCK_SENDER = "block_sender"
    BLOCK_DOMAIN = "block_domain"
    NOTIFY_USERS = "notify_users"
    DISABLE_ACCOUNT = "disable_account"
    RESET_CREDENTIALS = "reset_credentials"
    REVOKE_SESSIONS = "revoke_sessions"
    START_INVESTIGATION = "start_investigation"
    CONTAIN_CAMPAIGN = "contain_campaign"  # runs the bundle shown in the demo


class ContainmentRequest(BaseModel):
    action: ContainmentActionType
    campaign_id: str | None = None
    message_ids: list[str] = Field(default_factory=list)
    employee_ids: list[str] = Field(default_factory=list)
    sender: str | None = None
    domain: str | None = None
    approved_by: str  # admin employee id; containment always needs approval


class ContainmentResult(BaseModel):
    action: ContainmentActionType
    summary: str  # "14 messages would be quarantined"
    affected_count: int
    details: list[str] = Field(default_factory=list)
    at: datetime
    simulated: Literal[True] = True


class RecoveryTrack(BaseModel):
    name: str  # "Account protection", "Message containment", ...
    percent: int = Field(ge=0, le=100)


class ChecklistItem(BaseModel):
    id: str
    label: str
    done: bool = False


class RecoveryStatus(BaseModel):
    campaign_id: str | None = None
    incident_id: str | None = None
    tracks: list[RecoveryTrack]
    remaining_actions: list[ChecklistItem]
    simulated: Literal[True] = True
