"""Simulated containment actions. Every action needs an admin's approval,
changes only in-memory state, returns `simulated: true` and is audit-logged.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from urllib.parse import urlparse

from app.schemas import (
    ContainmentActionType,
    ContainmentRequest,
    ContainmentResult,
    Organization,
    SimEventType,
    TrackedLink,
)
from app.simulation.engine import AttackEngine
from app.simulation.events import EventBus, utcnow

logger = logging.getLogger(__name__)

Action = ContainmentActionType


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _domain_of(address: str) -> str:
    return address.rsplit("@", 1)[-1].lower()


class ContainmentService:
    def __init__(
        self,
        engine: AttackEngine,
        event_bus: EventBus,
        get_current_time: Callable[[], datetime] = utcnow,
    ):
        self.engine = engine
        self.event_bus = event_bus
        self.organization: Organization = engine.organization
        self._get_current_time = get_current_time
        self._employees_by_id = {employee.id: employee for employee in self.organization.employees}
        # Optional hook: called after a containment is applied, so the wiring can
        # record it against C's incident. Default does nothing (standalone sim).
        self.on_contained: Callable[[ContainmentRequest, list[ContainmentResult]], None] = lambda request, results: None
        self.reset()

    def reset(self) -> None:
        self.quarantined_message_ids: set[str] = set()
        self.blocked_senders: set[str] = set()
        self.blocked_domains: set[str] = set()
        self.notified_employee_ids: set[str] = set()
        self.revoked_session_employee_ids: set[str] = set()
        self.reset_credential_employee_ids: set[str] = set()
        self.disabled_employee_ids: set[str] = set()
        self.investigation_started = False
        # What the containment covered, for the recovery tracker.
        self.campaign_id: str | None = None
        self.scope_message_ids: set[str] = set()
        self.scope_recipient_ids: set[str] = set()
        self.affected_employee_ids: set[str] = set()
        self.audit_log: list[ContainmentResult] = []

    # -- queries used by the inbox, the click redirect and recovery ------------

    def is_message_contained(self, message_id: str) -> bool:
        """Quarantined, or from a blocked sender or domain (also future deliveries)."""
        if message_id in self.quarantined_message_ids:
            return True
        delivered_email = self.engine.delivered_emails_by_id.get(message_id)
        if delivered_email is None:
            return False
        sender = delivered_email.sender_address.lower()
        return sender in self.blocked_senders or _domain_of(sender) in self.blocked_domains

    def is_link_blocked(self, tracked_link: TrackedLink) -> bool:
        link_domain = (urlparse(tracked_link.url).hostname or "").lower()
        return self.is_message_contained(tracked_link.message_id) or link_domain in self.blocked_domains

    def is_account_disabled(self, employee_id: str) -> bool:
        return employee_id in self.disabled_employee_ids

    # -- applying actions ------------------------------------------------------

    def apply(self, request: ContainmentRequest) -> list[ContainmentResult]:
        """Run one action (or the campaign bundle). Raises PermissionError / ValueError."""
        approver = self._employees_by_id.get(request.approved_by)
        if approver is None or not approver.is_admin:
            raise PermissionError("containment must be approved by an admin")
        if request.campaign_id:
            self.campaign_id = request.campaign_id

        if request.action == Action.CONTAIN_CAMPAIGN:
            results = self._contain_campaign(request)
        else:
            results = [self._run(request.action, request)]

        for result in results:
            self.audit_log.append(result)
            self.event_bus.publish(
                SimEventType.CONTAINMENT_ACTION,
                data={"action": result.action.value, "summary": result.summary, "affected_count": result.affected_count},
            )
        try:
            self.on_contained(request, results)
        except Exception:
            logger.exception("on_contained hook failed for %s", request.action.value)
        return results

    def _contain_campaign(self, request: ContainmentRequest) -> list[ContainmentResult]:
        """The one-click bundle from the demo: quarantine, block, notify, protect accounts, investigate."""
        if not request.message_ids:
            raise ValueError("contain_campaign needs the campaign's message_ids")
        steps = [Action.QUARANTINE_MESSAGES, Action.BLOCK_SENDER, Action.BLOCK_DOMAIN, Action.NOTIFY_USERS]
        if request.employee_ids:
            steps += [Action.REVOKE_SESSIONS, Action.RESET_CREDENTIALS]
        steps.append(Action.START_INVESTIGATION)
        bundle_request = request.model_copy(update={"sender": None, "domain": None})
        return [self._run(step, bundle_request, notify_recipients_only=True) for step in steps]

    def _run(self, action: Action, request: ContainmentRequest, notify_recipients_only: bool = False) -> ContainmentResult:
        def result(summary: str, affected_count: int, details: list[str] | None = None) -> ContainmentResult:
            return ContainmentResult(
                action=action,
                approved_by=request.approved_by,
                summary=summary,
                affected_count=affected_count,
                details=details or [],
                at=self._get_current_time(),
            )

        if action == Action.QUARANTINE_MESSAGES:
            message_ids = self._delivered_message_ids(request)
            self.quarantined_message_ids |= message_ids
            self.scope_message_ids |= message_ids
            recipient_ids = self._recipients_of(message_ids)
            self.scope_recipient_ids |= recipient_ids
            return result(
                f"{_plural(len(message_ids), 'message')} quarantined",
                len(message_ids),
                [f"Removed from {_plural(len(recipient_ids), 'inbox')}"],
            )

        if action == Action.BLOCK_SENDER:
            senders = {request.sender.lower()} if request.sender else self._senders_of(request)
            self.blocked_senders |= senders
            summary = f"Sender {next(iter(senders))} blocked" if len(senders) == 1 else f"{len(senders)} senders blocked"
            return result(summary, len(senders), sorted(senders))

        if action == Action.BLOCK_DOMAIN:
            domains = {request.domain.lower()} if request.domain else {_domain_of(s) for s in self._senders_of(request)}
            self.blocked_domains |= domains
            summary = f"Domain {next(iter(domains))} blocked" if len(domains) == 1 else f"{len(domains)} domains blocked"
            return result(summary, len(domains), sorted(domains))

        if action == Action.NOTIFY_USERS:
            if request.employee_ids and not notify_recipients_only:
                employee_ids = self._known_employee_ids(request.employee_ids)
            else:
                employee_ids = self._recipients_of(self._delivered_message_ids(request))
            self.notified_employee_ids |= employee_ids
            self.scope_recipient_ids |= employee_ids
            return result(f"{_plural(len(employee_ids), 'employee')} notified", len(employee_ids), self._names(employee_ids))

        if action in (Action.REVOKE_SESSIONS, Action.RESET_CREDENTIALS, Action.DISABLE_ACCOUNT):
            employee_ids = self._known_employee_ids(request.employee_ids)
            if not employee_ids:
                raise ValueError(f"{action.value} needs employee_ids")
            self.affected_employee_ids |= employee_ids
            target_set, wording = {
                Action.REVOKE_SESSIONS: (self.revoked_session_employee_ids, "Sessions revoked for"),
                Action.RESET_CREDENTIALS: (self.reset_credential_employee_ids, "Password reset required for"),
                Action.DISABLE_ACCOUNT: (self.disabled_employee_ids, "Disabled"),
            }[action]
            target_set |= employee_ids
            return result(f"{wording} {_plural(len(employee_ids), 'account')}", len(employee_ids), self._names(employee_ids))

        if action == Action.START_INVESTIGATION:
            self.investigation_started = True
            flagged = len(self.affected_employee_ids)
            details = [f"{_plural(flagged, 'affected account')} flagged"] if flagged else []
            return result("Investigation started", 1, details)

        raise ValueError(f"unsupported action {action}")

    # -- helpers ---------------------------------------------------------------

    def _delivered_message_ids(self, request: ContainmentRequest) -> set[str]:
        if not request.message_ids:
            raise ValueError("message_ids are required")
        unknown = [m for m in request.message_ids if m not in self.engine.delivered_emails_by_id]
        if unknown:
            raise ValueError(f"unknown or not yet delivered messages: {', '.join(unknown)}")
        return set(request.message_ids)

    def _senders_of(self, request: ContainmentRequest) -> set[str]:
        return {
            self.engine.delivered_emails_by_id[m].sender_address.lower()
            for m in self._delivered_message_ids(request)
        }

    def _recipients_of(self, message_ids: set[str]) -> set[str]:
        return {r for m in message_ids for r in self.engine.delivered_emails_by_id[m].recipient_ids}

    def _known_employee_ids(self, employee_ids: list[str]) -> set[str]:
        unknown = [e for e in employee_ids if e not in self._employees_by_id]
        if unknown:
            raise ValueError(f"unknown employees: {', '.join(unknown)}")
        return set(employee_ids)

    def _names(self, employee_ids: set[str]) -> list[str]:
        return sorted(self._employees_by_id[e].name for e in employee_ids)
