"""Detection engine (Person A): .eml -> Message -> signals. Never executes anything."""

from app.detection.engine import detect
from app.detection.ingest import parse_eml
from app.detection.sim_eml import message_from_sim, render_eml

__all__ = ["detect", "message_from_sim", "parse_eml", "render_eml"]
