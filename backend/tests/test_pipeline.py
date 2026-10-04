"""D1: every delivered email is scored and ingested, with no employee action."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import session as db_session
from app.db.models import CampaignRow, EvidenceRow, MessageRow
from app.schemas import Severity
from app.simulation.engine import AttackEngine
from app.simulation.events import EventBus
from app.simulation.org_seed import seed_org
from app.simulation.pipeline import attach

ALICE = "e01"
AFTER_EVERYTHING = 10_000


class FakeClock:
    def __init__(self):
        self.t = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += timedelta(seconds=seconds)


@pytest.fixture
def db_factory():
    db_session.configure("sqlite://")  # fresh in-memory DB
    db_session.init_db()
    with db_session.SessionLocal() as db:
        seed_org(db)
    return db_session.SessionLocal


@pytest.fixture
def engine(db_factory):
    clock = FakeClock()
    engine = AttackEngine(EventBus(get_current_time=clock), get_current_time=clock,
                          public_base_url="http://sim.test")
    attach(engine, db_factory, use_ml=False)  # rules-only; no model needed
    return engine


def test_delivered_campaign_email_is_scored_high(engine, db_factory):
    engine.jump_to_demo_second(AFTER_EVERYTHING)
    with db_factory() as db:
        alice_msg = db.get(MessageRow, "cmp-01")
        assert alice_msg is not None
        assert alice_msg.recipient_id == ALICE
        assert alice_msg.risk >= int(Severity.HIGH)  # the demo gate: campaign scores HIGH+


def test_email_scored_evidence_is_filed_automatically(engine, db_factory):
    engine.jump_to_demo_second(AFTER_EVERYTHING)
    with db_factory() as db:
        evidence = db.scalars(
            select(EvidenceRow).where(EvidenceRow.kind == "email_scored", EvidenceRow.message_id == "cmp-01")
        ).all()
        assert len(evidence) == 1
        assert evidence[0].source == "automatic"  # not reported by the employee


def test_campaign_correlates_from_scored_messages(engine, db_factory):
    engine.jump_to_demo_second(AFTER_EVERYTHING)
    with db_factory() as db:
        campaigns = db.scalars(select(CampaignRow)).all()
        assert len(campaigns) >= 1
        grouped = db.scalars(
            select(MessageRow).where(MessageRow.campaign_id == campaigns[0].id)
        ).all()
        assert len(grouped) >= 2  # the Microsoft campaign messages cluster together


def test_legitimate_mail_scores_low(engine, db_factory):
    engine.jump_to_demo_second(AFTER_EVERYTHING)
    with db_factory() as db:
        invoice = db.get(MessageRow, "leg-02")  # a normal supplier invoice
        assert invoice is not None
        assert invoice.risk <= int(Severity.MEDIUM)
