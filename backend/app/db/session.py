from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base

engine = None
SessionLocal: sessionmaker | None = None


def configure(url: str | None = None) -> None:
    """Call once at startup (tests pass "sqlite://" for an in-memory DB)."""
    global engine, SessionLocal
    url = url or os.getenv("DATABASE_URL", "sqlite:///./security_copilot.db")
    kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if url in ("sqlite://", "sqlite:///:memory:"):
        kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def reset_db() -> None:
    """Drop everything. D's /api/sim/reset should call this, then re-seed."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def get_db():
    with SessionLocal() as db:
        yield db
