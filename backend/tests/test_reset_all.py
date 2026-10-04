"""D3: one call restores the whole demo — D's state and C's database."""

import pytest
from sqlalchemy import func, select

import app.simulation.runtime as runtime
from app.db import session as db_session
from app.db.models import EmployeeRow, EvidenceRow, IncidentRow, MessageRow
from app.simulation.org_seed import seed_org
from app.simulation.pipeline import reset_all

AFTER_EVERYTHING = 10_000


@pytest.fixture
def factory():
    db_session.configure("sqlite://")
    db_session.init_db()
    with db_session.SessionLocal() as db:
        seed_org(db)
    yield db_session.SessionLocal
    runtime.reset_demo()  # leave the shared runtime clean for other tests


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_reset_all_clears_db_and_state_but_reseeds_org(factory):
    # D in-memory state: deliver the whole mailbox (default hook, no DB writes).
    runtime.engine.reset()
    runtime.engine.jump_to_demo_second(AFTER_EVERYTHING)
    assert runtime.engine.status().delivered_count > 0

    # C database state: a scored message, an incident and its evidence.
    with factory() as db:
        db.add(MessageRow(id="cmp-01", recipient_id="e01", risk=3))
        db.add(IncidentRow(id="inc-1", severity=3))
        db.add(EvidenceRow(kind="password_reuse", employee_id="e01", source="automatic"))
        db.commit()
        assert _count(db, MessageRow) and _count(db, IncidentRow) and _count(db, EvidenceRow)

    reset_all(factory)

    assert runtime.engine.status().delivered_count == 0
    with factory() as db:
        assert _count(db, MessageRow) == 0
        assert _count(db, IncidentRow) == 0
        assert _count(db, EvidenceRow) == 0
        assert _count(db, EmployeeRow) == 24  # org re-seeded, ready to run again
