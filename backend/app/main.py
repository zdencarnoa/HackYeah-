"""Minimal skeleton. If the team already has a main.py, just copy the pieces you need."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import events, routes
from app.db import session


@asynccontextmanager
async def lifespan(app: FastAPI):
    events.bind_loop(asyncio.get_running_loop())
    if session.engine is None:  # tests configure their own DB first
        session.configure()
    session.init_db()
    yield


app = FastAPI(title="Security Copilot", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(events.router)
app.include_router(routes.router)
