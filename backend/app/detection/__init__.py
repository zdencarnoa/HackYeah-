"""Detection engine (Person A): .eml -> Message -> signals. Never executes anything.

HTTP routes live in app.detection.router (C mounts them).
"""

from app.detection.engine import detect
from app.detection.ingest import parse_eml
from app.detection.rewrite import clear_links, rewrite_links
from app.detection.sim_eml import message_from_sim, render_eml

__all__ = ["clear_links", "detect", "message_from_sim", "parse_eml", "render_eml", "rewrite_links"]
