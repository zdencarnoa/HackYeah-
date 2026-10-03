"""Delivery hook: D's mailbox calls this after A's link rewriting and B's /api/analyze."""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import EmployeeRow, MessageRow
from app.incidents.service import add_evidence
from app.schemas_proposal import Campaign, Evidence, MessageIn

from .correlation import correlate


class UnknownRecipient(ValueError):
    pass


def ingest_message(db: Session, msg: MessageIn) -> Campaign | None:
    emp = db.scalar(select(EmployeeRow).where(
        or_(EmployeeRow.email == msg.recipient.lower(), EmployeeRow.id == msg.recipient)))
    if emp is None:
        raise UnknownRecipient(msg.recipient)
    row = db.get(MessageRow, msg.id) or MessageRow(id=msg.id, recipient_id=emp.id)
    row.recipient_id, row.sender, row.subject, row.body = emp.id, msg.sender, msg.subject, msg.body
    row.urls, row.received_at, row.risk = list(msg.urls), msg.received_at, int(msg.risk)
    db.add(row)
    db.commit()
    add_evidence(db, Evidence(  # publishes message.scored; opens no incident by itself
        kind="email_scored", employee_id=emp.id, message_id=msg.id, risk=msg.risk,
        source="automatic", timestamp=msg.received_at))
    return correlate(db, msg.id)
