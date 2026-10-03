"""Simulated credential events: Chrome password reuse and a follow-up unusual sign-in.

A password typed on a domain outside ApprovedLogins produces a
PasswordReuseEvent, like Chrome Enterprise's PASSWORD_REUSE_EVENT. A few
seconds later the attacker "uses" it: an UNUSUAL_SIGN_IN event follows.
The password itself is never received, stored or sent anywhere.
"""

import asyncio
import base64
import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from urllib.parse import urlparse

from app.schemas import ApprovedLogin, Organization, PasswordReuseEvent, SimEventType
from app.simulation.events import EventBus, utcnow
from app.simulation.seed import load_approved_logins, load_org

logger = logging.getLogger(__name__)

PasswordReuseHook = Callable[[PasswordReuseEvent], None]

# Where the simulated attacker signs in from. 203.0.113.0/24 is reserved for documentation.
ATTACKER_SIGN_IN = {
    "ip": "203.0.113.200",
    "location": "Amsterdam, Netherlands",
    "device": "Windows 10, unknown browser",
    "result": "success",
}


def log_password_reuse(event: PasswordReuseEvent) -> None:
    """Default hook until C's password-reuse endpoint is plugged in."""
    logger.info("password reuse by %s on %s", event.employee_id, event.domain)


def to_pubsub_push(event: PasswordReuseEvent, subscription: str = "projects/demo/subscriptions/chrome-events") -> dict:
    """Wrap an event the way Google Pub/Sub delivers a push message."""
    return {
        "message": {
            "data": base64.b64encode(event.model_dump_json().encode()).decode(),
            "messageId": uuid.uuid4().hex,
            "publishTime": event.timestamp.isoformat(),
        },
        "subscription": subscription,
    }


class CredentialSimulator:
    def __init__(
        self,
        event_bus: EventBus,
        organization: Organization | None = None,
        approved_logins: list[ApprovedLogin] | None = None,
        on_password_reuse: PasswordReuseHook = log_password_reuse,
        unusual_sign_in_delay_seconds: float = 4.0,
        get_current_time: Callable[[], datetime] = utcnow,
    ):
        self.event_bus = event_bus
        self.organization = organization or load_org()
        self.approved_domains = {login.domain for login in (approved_logins or load_approved_logins())}
        self.on_password_reuse = on_password_reuse
        self.unusual_sign_in_delay_seconds = unusual_sign_in_delay_seconds
        self._get_current_time = get_current_time
        self._employees_by_id = {employee.id: employee for employee in self.organization.employees}
        self._pending_sign_ins: list[asyncio.TimerHandle] = []
        self.reset()

    def reset(self) -> None:
        for pending_sign_in in self._pending_sign_ins:
            pending_sign_in.cancel()
        self._pending_sign_ins = []
        self.password_reuse_events: list[PasswordReuseEvent] = []

    def is_approved_domain(self, domain: str) -> bool:
        return domain in self.approved_domains

    def record_password_entry(
        self, employee_id: str, page_url: str, message_id: str | None = None
    ) -> PasswordReuseEvent | None:
        """A password was typed on `page_url`. Returns the event, or None on an approved domain."""
        domain = urlparse(page_url).hostname or ""
        if self.is_approved_domain(domain):
            return None
        employee = self._employees_by_id[employee_id]
        event = PasswordReuseEvent(
            user=employee.email,
            employee_id=employee.id,
            url=page_url,
            domain=domain,
            reused_credential=employee.email,
            timestamp=self._get_current_time(),
        )
        self.password_reuse_events.append(event)
        self.event_bus.publish(
            SimEventType.PASSWORD_REUSE,
            employee_id=employee.id,
            message_id=message_id,
            data={"url": page_url, "domain": domain, "user": employee.email},
        )
        try:
            self.on_password_reuse(event)
        except Exception:
            logger.exception("password-reuse hook failed for %s", employee.id)
        self._schedule_unusual_sign_in(employee.id)
        return event

    def emit_unusual_sign_in(self, employee_id: str) -> None:
        self.event_bus.publish(SimEventType.UNUSUAL_SIGN_IN, employee_id=employee_id, data=dict(ATTACKER_SIGN_IN))

    def _schedule_unusual_sign_in(self, employee_id: str) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # no server running, e.g. in a plain test
            self.emit_unusual_sign_in(employee_id)
            return
        self._pending_sign_ins.append(
            loop.call_later(self.unusual_sign_in_delay_seconds, self.emit_unusual_sign_in, employee_id)
        )
