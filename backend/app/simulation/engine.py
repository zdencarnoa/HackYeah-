"""Attack engine: delivers the demo emails on a timeline, like a mail server.

On delivery each message loses its ground truth, gets per-recipient tracking
links (/r/{token}), lands in the simulated inboxes, is announced on the event
bus and is handed to ingestion through `on_deliver`.

See docs/attack_engine_explained.md for a walkthrough.
"""

import asyncio
import logging
import os
import secrets
from collections.abc import Callable, Iterable
from datetime import datetime
from urllib.parse import urlparse

from app.schemas import (
    AttackStatus,
    DeliveredEmail,
    InboxMessage,
    Organization,
    SimEmail,
    SimEventType,
    TrackedLink,
)
from app.simulation.events import EventBus, utcnow
from app.simulation.seed import load_emails, load_org

logger = logging.getLogger(__name__)

PUBLIC_BASE_URL = os.environ.get("SIM_PUBLIC_BASE_URL", "http://localhost:8000")

DeliveryHook = Callable[[DeliveredEmail], None]

# Attack scenarios that can be launched. Each one replays the whole demo mailbox
# (background mail plus the attack waves) on its timeline.
SCENARIOS = {"microsoft": "Operation Account Verification"}


def log_delivery(delivered_email: DeliveredEmail) -> None:
    """Default hook until C's ingestion is plugged in."""
    logger.info("delivered %s to %d recipients", delivered_email.id, len(delivered_email.recipient_ids))


class AttackEngine:
    def __init__(
        self,
        event_bus: EventBus,
        emails: Iterable[SimEmail] | None = None,
        organization: Organization | None = None,
        on_deliver: DeliveryHook = log_delivery,
        get_current_time: Callable[[], datetime] = utcnow,
        public_base_url: str = PUBLIC_BASE_URL,
    ):
        self.event_bus = event_bus
        self.organization = organization or load_org()
        self.on_deliver = on_deliver
        self._emails_in_delivery_order = sorted(
            emails if emails is not None else load_emails(),
            key=lambda email: email.deliver_offset_s,
        )
        self._ground_truth_by_message_id = {email.id: email.scenario for email in self._emails_in_delivery_order}
        self._get_current_time = get_current_time
        self._public_base_url = public_base_url.rstrip("/")
        self._employee_id_by_address = {employee.email: employee.id for employee in self.organization.employees}
        self._delivery_loop_task: asyncio.Task | None = None
        self.reset()

    # -- timeline ------------------------------------------------------------

    def reset(self) -> None:
        """Back to before the first delivery. Does not clear the event bus."""
        self._stop_delivery_loop()
        self._next_email_index = 0
        self._demo_seconds_banked = 0.0  # demo time collected before the current run
        self._run_started_at: datetime | None = None  # None while paused
        self.speed = 1.0
        self.scenario: str | None = None
        self.delivered_emails_by_id: dict[str, DeliveredEmail] = {}
        # The original SimEmail by id, so the delivery pipeline can render it to a
        # Message for scoring. Ground truth on it is never read outside the engine.
        self.sim_email_by_id: dict[str, SimEmail] = {}
        self.inbox_message_ids_by_employee: dict[str, list[str]] = {
            employee.id: [] for employee in self.organization.employees
        }
        self.tracked_links_by_token: dict[str, TrackedLink] = {}

    @property
    def is_running(self) -> bool:
        return self._run_started_at is not None

    @property
    def is_finished(self) -> bool:
        return self._next_email_index >= len(self._emails_in_delivery_order)

    def demo_seconds_elapsed(self) -> float:
        """How far the demo timeline has progressed, after the speed factor."""
        if self._run_started_at is None:
            return self._demo_seconds_banked
        real_seconds_since_start = (self._get_current_time() - self._run_started_at).total_seconds()
        return self._demo_seconds_banked + real_seconds_since_start * self.speed

    def status(self) -> AttackStatus:
        next_email = None if self.is_finished else self._emails_in_delivery_order[self._next_email_index]
        return AttackStatus(
            scenario=self.scenario,
            running=self.is_running,
            speed=self.speed,
            demo_seconds_elapsed=round(self.demo_seconds_elapsed(), 1),
            delivered_count=self._next_email_index,
            total_count=len(self._emails_in_delivery_order),
            next_message_id=next_email.id if next_email else None,
            next_delivery_at_seconds=next_email.deliver_offset_s if next_email else None,
        )

    def start(self, speed: float = 1.0, scenario: str = "microsoft") -> None:
        """Start or resume delivery. Calling it while running changes the speed."""
        if speed <= 0:
            raise ValueError("speed must be positive")
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario {scenario!r}")
        self.scenario = scenario
        if self.is_finished:
            return
        self._stop_clock_and_bank_time()
        self.speed = speed
        self._run_started_at = self._get_current_time()
        self._restart_delivery_loop()

    def pause(self) -> None:
        self._stop_clock_and_bank_time()
        self._stop_delivery_loop()

    def step(self) -> list[DeliveredEmail]:
        """Deliver the next message now; the timeline continues from its delivery time."""
        if self.is_finished:
            return []
        next_email = self._emails_in_delivery_order[self._next_email_index]
        return self.jump_to_demo_second(next_email.deliver_offset_s)

    def jump_to_demo_second(self, target_demo_second: float) -> list[DeliveredEmail]:
        """Move the timeline forward to `target_demo_second` and deliver everything due."""
        if target_demo_second > self.demo_seconds_elapsed():
            self._demo_seconds_banked = target_demo_second
            if self.is_running:
                self._run_started_at = self._get_current_time()
                self._restart_delivery_loop()
        return self.deliver_due_emails()

    def deliver_due_emails(self) -> list[DeliveredEmail]:
        """Deliver every email whose delivery time has been reached, in order."""
        current_demo_second = self.demo_seconds_elapsed()
        delivered_now = []
        while (
            not self.is_finished
            and self._emails_in_delivery_order[self._next_email_index].deliver_offset_s <= current_demo_second
        ):
            delivered_now.append(self._deliver(self._emails_in_delivery_order[self._next_email_index]))
            self._next_email_index += 1
        return delivered_now

    async def _delivery_loop(self) -> None:
        """Background task: deliver what is due, sleep until the next email, repeat."""
        while True:
            self.deliver_due_emails()
            if self.is_finished:
                break
            next_email = self._emails_in_delivery_order[self._next_email_index]
            demo_seconds_to_wait = next_email.deliver_offset_s - self.demo_seconds_elapsed()
            real_seconds_to_wait = demo_seconds_to_wait / self.speed
            await asyncio.sleep(max(real_seconds_to_wait, 0))
        self._stop_clock_and_bank_time()

    def _stop_clock_and_bank_time(self) -> None:
        self._demo_seconds_banked = self.demo_seconds_elapsed()
        self._run_started_at = None

    def _restart_delivery_loop(self) -> None:
        self._stop_delivery_loop()
        self._delivery_loop_task = asyncio.get_running_loop().create_task(self._delivery_loop())

    def _stop_delivery_loop(self) -> None:
        if self._delivery_loop_task is not None and not self._delivery_loop_task.done():
            self._delivery_loop_task.cancel()
        self._delivery_loop_task = None

    # -- delivery ------------------------------------------------------------

    def _expand_recipients(self, addresses: list[str]) -> list[str]:
        """Turn email addresses into employee ids; all@ becomes every employee."""
        everyone_address = f"all@{self.organization.domain}"
        employee_ids: list[str] = []
        for address in addresses:
            if address == everyone_address:
                employee_ids.extend(employee.id for employee in self.organization.employees)
            elif address in self._employee_id_by_address:
                employee_ids.append(self._employee_id_by_address[address])
        return list(dict.fromkeys(employee_ids))  # drop duplicates, keep order

    def _deliver(self, sim_email: SimEmail) -> DeliveredEmail:
        recipient_ids = self._expand_recipients(sim_email.to + sim_email.cc)
        tracked_links = []
        for employee_id in recipient_ids:
            for original_url in sim_email.urls:
                tracked_link = TrackedLink(
                    token=secrets.token_urlsafe(9),
                    message_id=sim_email.id,
                    employee_id=employee_id,
                    url=original_url,
                )
                self.tracked_links_by_token[tracked_link.token] = tracked_link
                tracked_links.append(tracked_link)
            self.inbox_message_ids_by_employee[employee_id].append(sim_email.id)

        delivered_email = DeliveredEmail(
            **sim_email.model_dump(exclude={"scenario", "deliver_offset_s"}),
            delivered_at=self._get_current_time(),
            recipient_ids=recipient_ids,
            links=tracked_links,
        )
        self.delivered_emails_by_id[sim_email.id] = delivered_email
        self.sim_email_by_id[sim_email.id] = sim_email
        self.event_bus.publish(
            SimEventType.EMAIL_DELIVERED,
            message_id=sim_email.id,
            data={"recipients": len(recipient_ids)},
        )
        try:
            self.on_deliver(delivered_email)
        except Exception:
            logger.exception("ingestion hook failed for %s", sim_email.id)
        return delivered_email

    # -- inboxes and clicks --------------------------------------------------

    def tracking_url(self, token: str) -> str:
        return f"{self._public_base_url}/r/{token}"

    def inbox(self, employee_id: str) -> list[InboxMessage]:
        """Newest first, with links rewritten to this employee's tracking links."""
        inbox_messages = []
        for message_id in reversed(self.inbox_message_ids_by_employee[employee_id]):
            delivered_email = self.delivered_emails_by_id[message_id]
            this_employees_links = [link for link in delivered_email.links if link.employee_id == employee_id]
            body_with_tracking_links = delivered_email.body_text
            html_with_tracking_links = delivered_email.body_html
            # Longest first, so a URL that is the start of a longer one can't break it.
            for link in sorted(this_employees_links, key=lambda link: len(link.url), reverse=True):
                tracking_url = self.tracking_url(link.token)
                body_with_tracking_links = body_with_tracking_links.replace(link.url, tracking_url)
                if html_with_tracking_links:
                    html_with_tracking_links = html_with_tracking_links.replace(link.url, tracking_url)
            inbox_messages.append(InboxMessage(
                id=delivered_email.id,
                sender_name=delivered_email.sender_name,
                sender_address=delivered_email.sender_address,
                reply_to=delivered_email.reply_to,
                subject=delivered_email.subject,
                body_text=body_with_tracking_links,
                body_html=html_with_tracking_links,
                links=this_employees_links,
                attachments=delivered_email.attachments,
                delivered_at=delivered_email.delivered_at,
            ))
        return inbox_messages

    def record_click(self, token: str) -> TrackedLink | None:
        """Record a click on a tracking link. Returns None for unknown tokens."""
        tracked_link = self.tracked_links_by_token.get(token)
        if tracked_link is None:
            return None
        self.event_bus.publish(
            SimEventType.LINK_CLICKED,
            employee_id=tracked_link.employee_id,
            message_id=tracked_link.message_id,
            data={"url": tracked_link.url, "domain": urlparse(tracked_link.url).hostname or ""},
        )
        return tracked_link

    def is_phishing(self, message_id: str) -> bool:
        """Ground truth, for the simulation's own routing only (never for detection)."""
        return self._ground_truth_by_message_id[message_id].label == "phishing"
