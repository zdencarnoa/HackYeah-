"""Evidence intake: the ONE entry point every producer uses (A's redirect, D's simulator,
the employee decision flow). Keeping a single function means the SSE event can never be
forgotten on some code path."""
from __future__ import annotations

import base64
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api import events
from app.db.models import ChecklistRow, EmployeeRow, EvidenceRow, IncidentRow, MessageRow
from app.schemas_proposal import (
    ChecklistItem,
    Evidence,
    Incident,
    Interaction,
    InteractionResult,
    PasswordReuseEvent,
    PubSubPush,
    Severity,
    TimelineItem,
)

from . import checklist
from .checklist_templates import incident_type_for
from .escalation import APPROVED_LOGINS, GUIDANCE, describe, severity_for

INVOICE_MIN_MESSAGES = 3  # a link-free money campaign opens a MEDIUM incident at this size


class ChecklistError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def as_utc(dt: datetime) -> datetime:
    # SQLite returns naive datetimes; we always store UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_evidence(r: EvidenceRow) -> Evidence:
    return Evidence(
        id=r.id, kind=r.kind, employee_id=r.employee_id, message_id=r.message_id,
        domain=r.domain, source=r.source, timestamp=as_utc(r.timestamp),
        interaction_kind=r.interaction_kind,
        risk=Severity(r.risk) if r.risk is not None else None,
    )


def _to_item(c: ChecklistRow) -> ChecklistItem:
    return ChecklistItem(
        id=c.id, key=c.key, action=c.action, rationale=c.rationale, area=c.area, done=c.done,
        needs_approval=c.needs_approval, containment_kind=c.containment_kind,
        approved_by=c.approved_by, approved_at=as_utc(c.approved_at) if c.approved_at else None,
        done_at=as_utc(c.done_at) if c.done_at else None)


def to_incident(db: Session, inc: IncidentRow) -> Incident:
    rows = db.scalars(
        select(EvidenceRow).where(EvidenceRow.incident_id == inc.id).order_by(EvidenceRow.timestamp)
    ).all()
    items = db.scalars(select(ChecklistRow).where(ChecklistRow.incident_id == inc.id)
                       .order_by(ChecklistRow.position)).all()
    evidence = [_to_evidence(r) for r in rows]
    return Incident(
        id=inc.id, type=inc.type, severity=Severity(inc.severity), campaign_id=inc.campaign_id,
        affected_employees=sorted({e.employee_id for e in evidence}),
        evidence=evidence,
        checklist=[_to_item(c) for c in items],
        timeline=[
            TimelineItem(timestamp=e.timestamp, employee_id=e.employee_id,
                         text=describe(e), source=e.source)
            for e in evidence
        ],
        created_at=as_utc(inc.created_at),
    )


def _campaign_of(db: Session, ev: Evidence) -> str | None:
    if not ev.message_id:
        return None
    msg = db.get(MessageRow, ev.message_id)
    return msg.campaign_id if msg else None


def _campaign_of_employee(db: Session, employee_id: str) -> str | None:
    """For events that carry no message (password reuse, unusual sign-in): the credential-phishing
    campaign (one with links) that most recently reached this employee. Link-free money campaigns
    are skipped so they can never swallow a password event."""
    rows = db.scalars(select(MessageRow).where(
        MessageRow.recipient_id == employee_id, MessageRow.campaign_id.is_not(None),
        MessageRow.risk >= int(Severity.HIGH)).order_by(MessageRow.received_at.desc())).all()
    for m in rows:
        if m.urls:
            return m.campaign_id
    return None


def _find_incident(db: Session, campaign_id: str | None, employee_id: str) -> IncidentRow | None:
    if campaign_id:
        inc = db.scalar(select(IncidentRow).where(
            IncidentRow.campaign_id == campaign_id, IncidentRow.status == "open"))
        if inc:
            return inc
    # Otherwise follow the employee, but only through real exposure evidence, never through
    # a plain "an email arrived" record.
    return db.scalar(
        select(IncidentRow)
        .join(EvidenceRow, EvidenceRow.incident_id == IncidentRow.id)
        .where(EvidenceRow.employee_id == employee_id, EvidenceRow.kind != "email_scored",
               IncidentRow.status == "open")
        .order_by(IncidentRow.created_at.desc())
    )


def add_evidence(db: Session, ev: Evidence) -> Incident | None:
    row = EvidenceRow(
        id=ev.id, kind=ev.kind, employee_id=ev.employee_id, message_id=ev.message_id,
        domain=ev.domain, source=ev.source, timestamp=ev.timestamp,
        interaction_kind=ev.interaction_kind, risk=int(ev.risk) if ev.risk is not None else None,
    )
    new_sev = severity_for(ev)

    if new_sev is None:  # stored, but opens nothing
        db.add(row)
        db.commit()
        if ev.kind == "email_scored":
            events.publish("message.scored", ev.model_dump(mode="json"))
        return None

    campaign_id = (_campaign_of(db, ev) if ev.message_id
                   else _campaign_of_employee(db, ev.employee_id))
    inc = _find_incident(db, campaign_id, ev.employee_id)
    created = inc is None
    if created:
        inc = IncidentRow(severity=int(new_sev), campaign_id=campaign_id)
        db.add(inc)
        db.flush()
    escalated = (not created) and new_sev > inc.severity
    if new_sev > inc.severity:
        inc.severity = int(new_sev)  # severity only ever goes up
    if inc.campaign_id is None and campaign_id:
        inc.campaign_id = campaign_id
    row.incident_id = inc.id
    db.add(row)
    checklist.sync_checklist(db, inc)
    db.commit()

    out = to_incident(db, inc)
    event = "incident.created" if created else "incident.escalated" if escalated else "incident.updated"
    events.publish(event, out.model_dump(mode="json"))
    return out


def handle_password_reuse(db: Session, push: PubSubPush) -> dict:
    """Pub/Sub push. Always answer 200 quickly, otherwise Pub/Sub retries."""
    try:
        reuse = PasswordReuseEvent.model_validate_json(base64.b64decode(push.message.data))
    except Exception:
        return {"ignored": "malformed payload"}
    domain = reuse.domain.strip().lower()
    if domain in APPROVED_LOGINS:
        return {"ignored": "approved login domain"}  # the "no false alarms" step of the demo
    emp = db.scalar(select(EmployeeRow).where(EmployeeRow.email == reuse.user.lower()))
    if not emp:
        return {"ignored": "unknown user"}
    # reuse.reused_credential is only a label; it is deliberately not stored.
    inc = add_evidence(db, Evidence(
        kind="password_reuse", employee_id=emp.id, domain=domain,
        source="automatic", timestamp=reuse.timestamp))
    return {"ok": True, "incident_id": inc.id if inc else None}


def record_interaction(db: Session, it: Interaction) -> InteractionResult:
    # What the system already knew before the employee answered ("We noticed you entered...").
    detected = sorted(set(db.scalars(select(EvidenceRow.kind).where(
        EvidenceRow.employee_id == it.employee_id,
        EvidenceRow.source == "automatic",
        EvidenceRow.kind.in_(["link_clicked", "password_reuse", "unusual_signin"]),
    )).all()))
    incident = None
    if it.kind != "none":
        incident = add_evidence(db, Evidence(
            kind="user_report", employee_id=it.employee_id, message_id=it.message_id,
            source="reported", interaction_kind=it.kind))
    return InteractionResult(guidance=GUIDANCE[it.kind], already_detected=detected, incident=incident)


def list_incidents(db: Session) -> list[Incident]:
    rows = db.scalars(select(IncidentRow).order_by(IncidentRow.created_at.desc())).all()
    return [to_incident(db, r) for r in rows]


def link_incidents_to_campaign(db: Session, campaign_id: str) -> None:
    """After correlation: attach incidents whose evidence touches the campaign's messages.
    If several exist (clicks that arrived before the campaign was known), merge them."""
    msg_ids = select(MessageRow.id).where(MessageRow.campaign_id == campaign_id)
    via_evidence = db.scalars(
        select(IncidentRow).join(EvidenceRow, EvidenceRow.incident_id == IncidentRow.id)
        .where(EvidenceRow.message_id.in_(msg_ids), IncidentRow.status == "open")).all()
    direct = db.scalars(select(IncidentRow).where(
        IncidentRow.campaign_id == campaign_id, IncidentRow.status == "open")).all()
    found = {i.id: i for i in [*via_evidence, *direct]}
    if not found:
        return
    incs = sorted(found.values(), key=lambda i: as_utc(i.created_at))
    keep, others = incs[0], incs[1:]
    before = keep.severity
    if not others and keep.campaign_id == campaign_id:
        return  # nothing changed
    for other in others:
        db.execute(update(EvidenceRow).where(EvidenceRow.incident_id == other.id)
                   .values(incident_id=keep.id))
        # items of the merged incident are dropped; the survivor regenerates what it needs
        for c in db.scalars(select(ChecklistRow).where(ChecklistRow.incident_id == other.id)).all():
            db.delete(c)
        keep.severity = max(keep.severity, other.severity)
        db.delete(other)
    keep.campaign_id = campaign_id
    checklist.sync_checklist(db, keep)
    db.commit()
    event = "incident.escalated" if keep.severity > before else "incident.updated"
    events.publish(event, to_incident(db, keep).model_dump(mode="json"))


def ensure_campaign_incident(db: Session, campaign_id: str) -> None:
    """Link-free money campaigns (invoice fraud) have no click to open an incident, so they get a
    MEDIUM incident once the campaign reaches INVOICE_MIN_MESSAGES. Idempotent."""
    msgs = db.scalars(select(MessageRow).where(MessageRow.campaign_id == campaign_id)).all()
    if len(msgs) < INVOICE_MIN_MESSAGES:
        return
    if incident_type_for((m.subject, m.body, list(m.urls or [])) for m in msgs) != "invoice_fraud":
        return
    inc = db.scalar(select(IncidentRow).where(
        IncidentRow.campaign_id == campaign_id, IncidentRow.status == "open"))
    created = inc is None
    if created:
        inc = IncidentRow(type="invoice_fraud", severity=int(Severity.MEDIUM), campaign_id=campaign_id)
        db.add(inc)
        db.flush()
    # affected employees and the timeline come from the delivery records of the campaign's mail
    unattached = db.scalars(select(EvidenceRow).where(
        EvidenceRow.kind == "email_scored", EvidenceRow.incident_id.is_(None),
        EvidenceRow.message_id.in_([m.id for m in msgs]))).all()
    for r in unattached:
        r.incident_id = inc.id
    added = checklist.sync_checklist(db, inc)
    if not (created or unattached or added):
        return
    db.commit()
    events.publish("incident.created" if created else "incident.updated",
                   to_incident(db, inc).model_dump(mode="json"))


# ---- checklist actions -------------------------------------------------------------------

def _item(db: Session, item_id: str) -> ChecklistRow:
    row = db.get(ChecklistRow, item_id)
    if row is None:
        raise ChecklistError(404, "checklist item not found")
    return row


def _publish_change(db: Session, incident_id: str) -> Incident:
    inc = db.get(IncidentRow, incident_id)
    out = to_incident(db, inc)
    events.publish("incident.updated", out.model_dump(mode="json"))
    events.publish("recovery.updated", checklist.progress(db, incident_id).model_dump(mode="json"))
    return out


def approve_item(db: Session, item_id: str, approved_by: str) -> Incident:
    """Admin approval only records consent. D's containment code runs the (simulated) action and
    then calls complete_item."""
    row = _item(db, item_id)
    if not row.needs_approval:
        raise ChecklistError(409, "this step does not need approval")
    if row.approved_by is None:
        row.approved_by, row.approved_at = approved_by, _now()
    db.commit()
    return _publish_change(db, row.incident_id)


def approve_all(db: Session, incident_id: str, approved_by: str) -> Incident:
    if db.get(IncidentRow, incident_id) is None:
        raise ChecklistError(404, "incident not found")
    for r in db.scalars(select(ChecklistRow).where(
            ChecklistRow.incident_id == incident_id, ChecklistRow.needs_approval.is_(True),
            ChecklistRow.approved_by.is_(None))).all():
        r.approved_by, r.approved_at = approved_by, _now()
    db.commit()
    return _publish_change(db, incident_id)


def complete_item(db: Session, item_id: str, done: bool = True) -> Incident:
    row = _item(db, item_id)
    if done and row.needs_approval and row.approved_by is None:
        raise ChecklistError(409, "waiting for admin approval")
    row.done, row.done_at = done, (_now() if done else None)
    db.commit()
    return _publish_change(db, row.incident_id)
