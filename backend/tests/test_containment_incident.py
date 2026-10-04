"""D4: approving "Contain campaign" marks the open incident contained in C."""

import pytest
from sqlalchemy import select

from app.db import session as db_session
from app.db.models import IncidentRow
from app.schemas import ContainmentActionType as Action
from app.schemas import ContainmentRequest
from app.simulation.containment import ContainmentService
from app.simulation.credentials import CredentialSimulator
from app.simulation.engine import AttackEngine
from app.simulation.events import EventBus
from app.simulation.org_seed import seed_org
from app.simulation.pipeline import attach, attach_containment, attach_credentials

ALICE = "e01"
ADMIN = "e15"
PHISH_URL = "https://micr0soft-verify.example/verify?session=7f3a00c9"
AFTER_EVERYTHING = 10_000


@pytest.fixture
def world():
    db_session.configure("sqlite://")
    db_session.init_db()
    with db_session.SessionLocal() as db:
        seed_org(db)
    factory = db_session.SessionLocal
    bus = EventBus()
    engine = AttackEngine(bus)
    credentials = CredentialSimulator(bus, unusual_sign_in_delay_seconds=0)
    containment = ContainmentService(engine, bus)
    attach(engine, factory, use_ml=False)
    attach_credentials(credentials, factory)
    attach_containment(containment, factory)
    return engine, credentials, containment, factory


def _campaign_message_ids(engine):
    return [m for m in engine.delivered_emails_by_id if m.startswith("cmp-")]


def test_contain_campaign_marks_the_incident_contained(world):
    engine, credentials, containment, factory = world
    engine.jump_to_demo_second(AFTER_EVERYTHING)          # D1: all mail scored, campaign correlated
    credentials.record_password_entry(ALICE, PHISH_URL)    # D2: CRITICAL incident opens for Alice

    with factory() as db:
        incident = db.scalar(select(IncidentRow))
        assert incident is not None and incident.status == "open"

    containment.apply(ContainmentRequest(
        action=Action.CONTAIN_CAMPAIGN,
        message_ids=_campaign_message_ids(engine),
        employee_ids=[ALICE],
        approved_by=ADMIN,
    ))

    with factory() as db:
        incident = db.scalar(select(IncidentRow))
        assert incident.status == "contained"


def test_containment_still_needs_admin_approval(world):
    engine, credentials, containment, factory = world
    engine.jump_to_demo_second(AFTER_EVERYTHING)
    with pytest.raises(PermissionError):
        containment.apply(ContainmentRequest(
            action=Action.QUARANTINE_MESSAGES, message_ids=["cmp-01"], approved_by=ALICE))
