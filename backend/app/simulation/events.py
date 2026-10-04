"""In-process event bus for simulated events (deliveries, clicks, password reuse, ...)."""

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from app.schemas import SimEvent, SimEventType

logger = logging.getLogger(__name__)

Subscriber = Callable[[SimEvent], None]


def utcnow() -> datetime:
    return datetime.now(UTC)


class EventBus:
    """Keeps a history of every event and forwards each one to subscribers.

    C's SSE stream subscribes here, e.g. with a function that does
    `queue.put_nowait(event)`. A failing subscriber never blocks the others.
    """

    def __init__(self, get_current_time: Callable[[], datetime] = utcnow):
        self._get_current_time = get_current_time
        self._subscribers: list[Subscriber] = []
        self.event_history: list[SimEvent] = []

    def subscribe(self, subscriber: Subscriber) -> Callable[[], None]:
        """Register `subscriber`; returns a function that unsubscribes it."""
        self._subscribers.append(subscriber)
        return lambda: self._subscribers.remove(subscriber)

    def publish(
        self,
        event_type: SimEventType,
        *,
        employee_id: str | None = None,
        message_id: str | None = None,
        data: dict[str, str | int | bool] | None = None,
    ) -> SimEvent:
        event = SimEvent(
            id=uuid.uuid4().hex,
            type=event_type,
            at=self._get_current_time(),
            employee_id=employee_id,
            message_id=message_id,
            data=data or {},
        )
        self.event_history.append(event)
        for subscriber in list(self._subscribers):
            try:
                subscriber(event)
            except Exception:
                logger.exception("event subscriber failed on %s", event.type)
        return event

    def clear_history(self) -> None:
        self.event_history.clear()
