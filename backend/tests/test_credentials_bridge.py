"""D2: a password entered on a phishing page creates a CRITICAL incident in C,
with no employee report."""

import pytest
from sqlalchemy import select

from app.db import session as db_session
from app.db.models import EvidenceRow, IncidentRow
from app.schemas import Severity
from app.simulation.credentials import CredentialSimulator
from app.simulation.events import EventBus
from app.simulation.org_seed import seed_org
from app.simulation.pipeline import attach_credentials

ALICE = "e01"
ALICE_EMAIL = "alice.johnson@lakeside-logistics.example"
PHISH_URL = "https://micr0soft-verify.example/verify?session=7f3a00c9"


@pytest.fixture
def db_factory():
    db_session.configure("sqlite://")
    db_session.init_db()
    with db_session.SessionLocal() as db:
        seed_org(db)
    return db_session.SessionLocal


@pytest.fixture
def credentials(db_factory):
    creds = CredentialSimulator(EventBus(), unusual_sign_in_delay_seconds=0)
    attach_credentials(creds, db_factory)
    return creds


def test_password_on_phishing_page_opens_an_incident(credentials, db_factory):
    credentials.record_password_entry(ALICE, PHISH_URL, message_id="cmp-01")
    with db_factory() as db:
        evidence = db.scalars(
            select(EvidenceRow).where(EvidenceRow.employee_id == ALICE, EvidenceRow.kind == "password_reuse")
        ).all()
        assert len(evidence) == 1 and evidence[0].source == "automatic"
        incident = db.scalar(select(IncidentRow))
        assert incident is not None
        assert incident.severity >= int(Severity.CRITICAL)


def test_follow_up_unusual_sign_in_joins_the_timeline(credentials, db_factory):
    credentials.record_password_entry(ALICE, PHISH_URL)  # delay=0 fires the sign-in at once
    with db_factory() as db:
        kinds = set(db.scalars(select(EvidenceRow.kind).where(EvidenceRow.employee_id == ALICE)).all())
        assert {"password_reuse", "unusual_signin"} <= kinds


def test_password_on_approved_domain_is_silent(credentials, db_factory):
    approved = "https://login.lakeside-logistics.example/password"
    assert credentials.record_password_entry(ALICE, approved) is None  # simulator never fires
    with db_factory() as db:
        assert db.scalar(select(IncidentRow)) is None
