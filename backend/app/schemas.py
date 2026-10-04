"""Shared contracts between backend areas and the frontend.

One source of truth for every area: simulation (D), detection (A), the risk
verdict (B), and incidents & campaigns (C). Changes are agreed with the team
because the frontend and the other areas build against this file.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import IntEnum, StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return uuid4().hex[:12]


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
    # Optional HTML part. Its links keep their anchor text, so a link can show
    # one address and lead to another.
    body_html: str | None = None
    urls: list[str] = Field(default_factory=list)  # as they appear in the body
    attachments: list[Attachment] = Field(default_factory=list)
    auth: AuthResults
    sending_ip: str
    # Seconds after demo start when the attack engine delivers this message.
    deliver_offset_s: int
    scenario: ScenarioLabel


class TrackedLink(BaseModel):
    """A link rewritten to /r/{token} for one recipient, so clicks are traceable."""

    token: str
    message_id: str
    employee_id: str
    url: str  # the original link


class DeliveredEmail(BaseModel):
    """What ingestion receives when the attack engine delivers a message.

    Same as SimEmail without the ground truth. `body_text` and `urls` are the
    originals so analyzers see the real destinations; `links` holds the
    rewritten per-recipient tracking links.
    """

    id: str
    sender_name: str
    sender_address: str
    reply_to: str | None = None
    to: list[str]
    cc: list[str] = Field(default_factory=list)
    subject: str
    body_text: str
    body_html: str | None = None
    urls: list[str] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    auth: AuthResults
    sending_ip: str
    delivered_at: datetime
    recipient_ids: list[str]  # employee ids, with all@ expanded
    links: list[TrackedLink] = Field(default_factory=list)


class InboxMessage(BaseModel):
    """One message as shown in an employee's simulated inbox."""

    id: str
    sender_name: str
    sender_address: str
    reply_to: str | None = None
    subject: str
    body_text: str  # links already rewritten to this employee's /r/{token}
    body_html: str | None = None  # links also rewritten
    links: list[TrackedLink]
    attachments: list[Attachment] = Field(default_factory=list)
    delivered_at: datetime


class AttackStatus(BaseModel):
    scenario: str | None = None
    running: bool
    speed: float
    demo_seconds_elapsed: float  # demo time since start, after the speed factor
    delivered_count: int
    total_count: int
    next_message_id: str | None = None
    next_delivery_at_seconds: int | None = None


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


class PasswordReuseEvent(BaseModel):
    """Simulated Chrome Enterprise PASSWORD_REUSE_EVENT.

    Fired when a company password is typed on a domain outside ApprovedLogins.
    Never contains the password itself.
    """

    event_type: Literal["passwordReuseEvent"] = "passwordReuseEvent"
    user: str  # employee email, the account whose password was reused
    employee_id: str | None = None  # the simulator fills this; a real Chrome feed would not
    url: str
    domain: str
    reused_credential: str = "work_account"  # label only, never the password
    timestamp: datetime = Field(default_factory=_now)
    simulated: bool = True


class BlastRadiusNode(BaseModel):
    id: str
    label: str
    kind: BlastNodeKind
    sensitivity: Sensitivity | None = None
    at_risk: bool  # reachable from the compromised account
    reason: str  # why it is (or is not) reachable, in plain language


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
    approved_by: str
    summary: str  # "14 messages would be quarantined"
    affected_count: int
    details: list[str] = Field(default_factory=list)
    at: datetime
    simulated: Literal[True] = True


class RecoveryTrack(BaseModel):
    name: str  # "Account protection", "Message containment", ...
    percent: int = Field(ge=0, le=100)


class RecoveryChecklistItem(BaseModel):
    id: str
    label: str
    done: bool = False


class RecoveryStatus(BaseModel):
    campaign_id: str | None = None
    incident_id: str | None = None
    tracks: list[RecoveryTrack]
    remaining_actions: list[RecoveryChecklistItem]
    simulated: Literal[True] = True


# ---------------------------------------------------------------------------
# Detection (Person A): a parsed message as every analyzer sees it. Built by
# app.detection.parse_eml from an uploaded .eml, or from a SimEmail rendered to
# .eml on delivery, so both paths produce exactly the same shape.
# ---------------------------------------------------------------------------


class Link(BaseModel):
    # As written in the href or the text. Bare "www." links get "http://".
    url: str
    anchor_text: str | None = None  # visible text of the <a>; None for text links
    found_in: Literal["text", "html"]


class MessageAttachment(Attachment):
    # A zip whose entries carry the encryption flag. Read from the zip's table
    # of contents in memory; attachments are never unpacked or executed.
    encrypted: bool = False


class Message(BaseModel):
    id: str  # SimEmail.id for demo mail; for uploads a hash of Message-ID + recipients
    sender: str  # "security@micr0soft-example.test", lowercased
    sender_name: str  # "Microsoft Security"; "" when From has no display name
    reply_to: str | None = None
    recipients: list[str]  # To + Cc, lowercased
    subject: str
    body_text: str  # the text/plain part, else the visible text of the HTML part
    body_html: str | None = None
    urls: list[Link] = Field(default_factory=list)  # web links only, deduplicated
    attachments: list[MessageAttachment] = Field(default_factory=list)
    headers: list[tuple[str, str]] = Field(default_factory=list)  # repeats kept, in order
    received_at: datetime  # from the Date header; the parse time if missing or broken


class SignalCategory(StrEnum):
    # Task 2: headers
    AUTH_FAILURE = "auth_failure"
    REPLY_TO_MISMATCH = "reply_to_mismatch"
    RETURN_PATH_MISMATCH = "return_path_mismatch"
    # Task 3: who the sender claims to be
    BRAND_IMPERSONATION = "brand_impersonation"
    FREEMAIL_IMPERSONATION = "freemail_impersonation"
    COLLEAGUE_IMPERSONATION = "colleague_impersonation"
    # Tasks 4 and 5: domains and links
    LOOKALIKE_DOMAIN = "lookalike_domain"
    SUSPICIOUS_URL = "suspicious_url"
    # Task 6: content
    URGENCY = "urgency"
    CREDENTIAL_REQUEST = "credential_request"
    PAYMENT_CHANGE = "payment_change"
    GIFT_CARD = "gift_card"
    MFA_CODE_REQUEST = "mfa_code_request"
    # Task 7: attachments
    RISKY_ATTACHMENT = "risky_attachment"
    # Task 8: offline blocklist
    KNOWN_BAD = "known_bad"
    # Person B's classifier
    ML_PHISHING = "ml_phishing"


class Signal(BaseModel):
    """One concrete, checkable fact about a message. Never a verdict: only B's
    risk fusion sets the risk level."""

    id: str  # stable rule id such as "header.auth"; at most one signal per rule
    category: SignalCategory
    # 0 context only, 1 weak (common in legitimate mail too), 2 moderate,
    # 3 strong (rarely seen in legitimate mail)
    severity: int = Field(ge=0, le=3)
    evidence: str  # one plain-language sentence, shown to employees as-is
    technical_detail: str  # jargon for "Advanced details", e.g. "spf=fail; dmarc=fail"
    source: Literal["rule", "url", "ml", "intel"]


class DetectionResult(BaseModel):
    signals: list[Signal] = Field(default_factory=list)
    # Checks that could not run, in plain language, for B's uncertainties[]:
    # "We could not check ... because the email has no authentication results."
    unchecked: list[str] = Field(default_factory=list)


class SignalsResponse(DetectionResult):
    """POST /api/analyze/signals: an uploaded .eml, parsed, with its signals.
    For debugging and the UI's "Advanced details"; B's /api/analyze is the main path."""

    message: Message


# ---------------------------------------------------------------------------
# Risk verdict (Person B): the fused risk level and the grounded explanation.
# Risk fusion sets `risk`; the LLM only writes the explanation.
# ---------------------------------------------------------------------------


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
    ml_confidence: float | None = None  # calibrated phishing probability 0-1; None if unavailable
    ml_model: str | None = None  # "distilbert-v1" or "tfidf-fallback"
    uncertainties: list[str] = Field(default_factory=list)  # what could not be checked
    explanation: Explanation
    recommended_action: str  # every result ends with a next action
    assessed_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Incidents & campaigns (Person C): evidence intake, incident timeline and
# campaign correlation. The decision flow and the admin dashboard read these.
# ---------------------------------------------------------------------------


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
    interaction_kind: InteractionKind | None = None  # only for user_report
    risk: Severity | None = None  # only for email_scored


class TimelineItem(BaseModel):
    timestamp: datetime
    employee_id: str
    text: str  # plain language
    source: Literal["automatic", "reported"]  # UI shows Automatic / Reported tag


class ChecklistItem(BaseModel):
    """An incident-response step. (The recovery progress list uses RecoveryChecklistItem.)"""

    action: str
    rationale: str
    done: bool = False


class Incident(BaseModel):
    id: str
    type: str
    severity: Severity
    status: str = "open"  # "open" until containment runs, then "contained"
    campaign_id: str | None = None
    affected_employees: list[str]
    evidence: list[Evidence]
    checklist: list[ChecklistItem] = Field(default_factory=list)
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


class PubSubMessage(BaseModel):
    data: str  # base64(JSON PasswordReuseEvent)
    messageId: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)


class PubSubPush(BaseModel):
    message: PubSubMessage
    subscription: str | None = None


class MessageIn(BaseModel):
    """A's Message fields C needs, plus B's risk level. The delivery glue builds
    this from a DeliveredEmail and its Assessment."""

    id: str
    sender: str
    recipient: str  # employee email (or id)
    subject: str
    body: str
    urls: list[str] = Field(default_factory=list)  # original URLs, before link rewriting
    received_at: datetime = Field(default_factory=_now)
    risk: Severity  # from B's Assessment


class Campaign(BaseModel):
    id: str
    name: str
    message_ids: list[str]
    recipients: list[str]
    departments: list[str]
    shared_traits: list[str]  # plain-language observations
    incident_id: str | None = None  # lets the UI jump from campaign to incident
    updated_at: datetime
