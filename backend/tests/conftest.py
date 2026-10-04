import pytest
from fastapi.testclient import TestClient

from app.api import events
from app.db import session
from app.db.seed import seed_minimal


@pytest.fixture
def ctx(monkeypatch):
    session.configure("sqlite://")
    session.init_db()
    with session.SessionLocal() as db:
        seed_minimal(db)
    published = []
    monkeypatch.setattr(events, "publish", lambda t, p: published.append((t, p)))
    from app.main import app
    with TestClient(app) as client:
        yield client, published
