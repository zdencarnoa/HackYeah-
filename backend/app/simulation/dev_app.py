"""Standalone app for working on the simulation before C's main app exists.

Run from backend/:  ..\\.venv\\Scripts\\python -m uvicorn app.simulation.dev_app:app --reload
"""

import logging

from fastapi import FastAPI

from app.simulation.router import router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Security Copilot - simulation (dev)")
app.include_router(router)
