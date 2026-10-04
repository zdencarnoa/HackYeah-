"""Minimal skeleton. If the team already has a main.py, just copy the pieces you need."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import func, select

from app.api import events, routes
from app.db import session
from app.db.models import EmployeeRow
from app.detection.router import router as detection_router
from app.scoring.ml_signal import warm_up
from app.scoring.router import router as scoring_router
from app.simulation import pipeline, runtime
from app.simulation.org_seed import seed_org
from app.simulation.router import api_router as sim_api_router
from app.simulation.router import router as sim_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    events.bind_loop(asyncio.get_running_loop())
    if session.engine is None:  # tests configure their own DB first
        session.configure()
    session.init_db()

    # Seed D's organization once (skip if a DB already has employees).
    with session.SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(EmployeeRow)) == 0:
            seed_org(db)

    # Wire the simulation to the live pipeline: score on delivery, route
    # password reuse to incidents, link containment. A late-binding factory keeps
    # using whichever DB is configured; unwire on shutdown so nothing leaks.
    # B's classifier is loaded once here, so delivery scoring uses the same rules + ML
    # verdict as "Is this safe?" without a delay on the first email. Without the ML
    # packages or weights, warm_up() returns None and scoring runs on rules alone.
    ml_model = await asyncio.to_thread(warm_up)
    unwire = pipeline.wire_live(
        runtime.engine, runtime.credentials, runtime.containment,
        session_factory=lambda: session.SessionLocal(), use_ml=ml_model is not None,
    )
    try:
        yield
    finally:
        unwire()


app = FastAPI(title="Security Copilot", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(events.router)
app.include_router(routes.router)
# Simulation first: it owns the live /r/{token} click path (the attack engine
# rewrites links and serves the inbox), so it takes precedence over detection's
# own /r used for uploaded-email analysis.
app.include_router(sim_router)
app.include_router(sim_api_router)
app.include_router(detection_router)
app.include_router(scoring_router)
