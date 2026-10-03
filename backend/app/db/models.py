from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _id() -> str:
    return uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class EmployeeRow(Base):
    __tablename__ = "employees"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    department: Mapped[str] = mapped_column(String)


class CampaignRow(Base):
    __tablename__ = "campaigns"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: f"camp-{_id()[:6]}")
    name: Mapped[str] = mapped_column(String, default="Suspicious emails")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MessageRow(Base):
    """Delivered message as C needs it for correlation. campaign_id is filled by correlation."""

    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    recipient_id: Mapped[str] = mapped_column(String, index=True)
    sender: Mapped[str] = mapped_column(String, default="")
    subject: Mapped[str] = mapped_column(String, default="")
    body: Mapped[str] = mapped_column(String, default="")
    urls: Mapped[list] = mapped_column(JSON, default=list)  # ORIGINAL urls, before /r/{token} rewriting
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    risk: Mapped[int | None] = mapped_column(Integer, nullable=True)
    campaign_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)


class IncidentRow(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    type: Mapped[str] = mapped_column(String, default="credential_phishing")
    severity: Mapped[int] = mapped_column(Integer)
    campaign_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EvidenceRow(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    kind: Mapped[str] = mapped_column(String)
    employee_id: Mapped[str] = mapped_column(String, index=True)
    message_id: Mapped[str | None] = mapped_column(String, nullable=True)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    interaction_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    risk: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incident_id: Mapped[str | None] = mapped_column(
        ForeignKey("incidents.id"), index=True, nullable=True
    )
