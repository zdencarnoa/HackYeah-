"""A click in a suspicious email becomes link_clicked evidence (demo step 3: "Possible exposure: Alice");
a click in a legitimate email does not open an incident."""

import pytest
from sqlalchemy import select

from app.db import session as db_session
from app.db.models import EvidenceRow, IncidentRow
from app.schemas import Severity
from app.simulation.credentials import CredentialSimulator
from app.simulation.engine import AttackEngine
from app.simulation.events import EventBus
from app.simulation.org_seed import seed_org
from app.simulation.pipeline import attach, attach_credentials

ALICE = "e01"
AFTER_EVERYTHING = 10_000


@pytest.fixture
def world():
    db_session.configure("sqlite://")
    db_session.init_db()
    with db_session.SessionLocal() as db:
        seed_org(db)
    bus = EventBus()
    engine = AttackEngine(bus)
    attach(engine, db_session.SessionLocal, use_ml=False)
    attach_credentials(CredentialSimulator(bus, unusual_sign_in_delay_seconds=0), db_session.SessionLocal)
    engine.jump_to_demo_second(AFTER_EVERYTHING)
    return engine


def _alice_link(engine, phishing: bool):
    for message in engine.inbox(ALICE):
        if message.links and engine.is_phishing(message.id) == phishing:
            return message.links[0]
    pytest.skip("no such link in Alice's inbox")


def test_click_in_phishing_email_opens_a_high_incident(world):
    link = _alice_link(world, phishing=True)
    world.record_click(link.token)
    with db_session.SessionLocal() as db:
        clicks = db.scalars(select(EvidenceRow).where(EvidenceRow.kind == "link_clicked")).all()
        assert [(c.employee_id, c.message_id) for c in clicks] == [(ALICE, link.message_id)]
        incident = db.get(IncidentRow, clicks[0].incident_id)
        assert incident.severity == Severity.HIGH


def test_click_in_legitimate_email_is_not_evidence(world):
    link = _alice_link(world, phishing=False)
    world.record_click(link.token)
    with db_session.SessionLocal() as db:
        assert db.scalars(select(EvidenceRow).where(EvidenceRow.kind == "link_clicked")).all() == []
