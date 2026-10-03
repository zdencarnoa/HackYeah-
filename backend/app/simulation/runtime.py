"""The single engine and event bus used by the running app.

Other areas import these, e.g. C plugs in ingestion with
`engine.on_deliver = ingest` and streams `event_bus` events over SSE.
"""

from app.simulation.engine import AttackEngine
from app.simulation.events import EventBus

event_bus = EventBus()
engine = AttackEngine(event_bus)
