"""Recovery tracker: progress per area, computed from the containment state
plus a short checklist the admin ticks off by hand.
"""

from app.schemas import RecoveryChecklistItem, RecoveryStatus, RecoveryTrack
from app.simulation.containment import ContainmentService

# (id, label). Automatic items are done when containment did them.
AUTOMATIC_ITEMS = [
    ("investigation_opened", "Investigation opened"),
    ("messages_quarantined", "Campaign messages quarantined"),
    ("sender_blocked", "Sender infrastructure blocked"),
    ("users_notified", "Affected users notified"),
]
MANUAL_ITEMS = [
    ("review_account_activity", "Review account activity"),
    ("confirm_password_reset", "Confirm password reset"),
    ("complete_incident_report", "Complete incident report"),
]
MANUAL_ITEM_IDS = {item_id for item_id, _ in MANUAL_ITEMS}


def _percent(done: int, total: int) -> int:
    return round(100 * done / total) if total else 0


class RecoveryTracker:
    def __init__(self, containment: ContainmentService):
        self.containment = containment
        self.reset()

    def reset(self) -> None:
        self.manually_done_item_ids: set[str] = set()

    def mark_done(self, item_id: str) -> None:
        if item_id not in MANUAL_ITEM_IDS:
            raise KeyError(item_id)
        self.manually_done_item_ids.add(item_id)

    def checklist(self) -> list[RecoveryChecklistItem]:
        c = self.containment
        automatic_done = {
            "investigation_opened": c.investigation_started,
            "messages_quarantined": bool(c.quarantined_message_ids),
            "sender_blocked": bool(c.blocked_senders or c.blocked_domains),
            "users_notified": bool(c.notified_employee_ids),
        }
        return [RecoveryChecklistItem(id=i, label=label, done=automatic_done[i]) for i, label in AUTOMATIC_ITEMS] + [
            RecoveryChecklistItem(id=i, label=label, done=i in self.manually_done_item_ids) for i, label in MANUAL_ITEMS
        ]

    def status(self) -> RecoveryStatus:
        c = self.containment
        checklist = self.checklist()

        affected = c.affected_employee_ids
        protection_steps_done = len(affected & c.revoked_session_employee_ids) + len(affected & c.reset_credential_employee_ids)
        if affected:
            account_protection = _percent(protection_steps_done, 2 * len(affected))
        else:
            account_protection = 100 if c.scope_message_ids else 0  # nothing to protect once contained

        contained_count = sum(1 for m in c.scope_message_ids if c.is_message_contained(m))
        notified_count = len(c.scope_recipient_ids & c.notified_employee_ids)

        return RecoveryStatus(
            campaign_id=c.campaign_id,
            tracks=[
                RecoveryTrack(name="Account protection", percent=account_protection),
                RecoveryTrack(name="Message containment", percent=_percent(contained_count, len(c.scope_message_ids))),
                RecoveryTrack(name="Affected users notified", percent=_percent(notified_count, len(c.scope_recipient_ids))),
                RecoveryTrack(name="Investigation", percent=_percent(sum(i.done for i in checklist), len(checklist))),
            ],
            remaining_actions=[item for item in checklist if not item.done],
        )
