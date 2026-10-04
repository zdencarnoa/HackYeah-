"""The single set of simulation objects used by the running app.

Other areas import these, e.g. C plugs in ingestion with
`engine.on_deliver = ingest`, password reuse with
`credentials.on_password_reuse = handle`, and streams `event_bus` events over SSE.
"""

from app.schemas import SimEventType
from app.simulation.containment import ContainmentService
from app.simulation.credentials import CredentialSimulator
from app.simulation.engine import AttackEngine
from app.simulation.events import EventBus
from app.simulation.recovery import RecoveryTracker

event_bus = EventBus()
engine = AttackEngine(event_bus)
credentials = CredentialSimulator(event_bus, organization=engine.organization)
containment = ContainmentService(engine, event_bus)
recovery = RecoveryTracker(containment)


def reset_demo() -> None:
    """Back to the starting state: nothing delivered, nothing contained, no events."""
    engine.reset()
    credentials.reset()
    containment.reset()
    recovery.reset()
    event_bus.clear_history()
    event_bus.publish(SimEventType.DEMO_RESET)  # tells C and the UI to clear their state too
