"""Response-checklist templates. Pure Python (no DB, no pydantic).

Rationales are deliberately hedged: they say what the evidence suggests, never what the
attacker did. Person B's LLM may rewrite the rationale; these are the offline fallback.
Containment items (needs_approval) wait for the admin; D executes them as simulations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

MEDIUM, HIGH, CRITICAL = 1, 2, 3  # same numbers as Severity
AREAS = ("account", "messages", "notifications", "investigation")  # D's recovery tracker


@dataclass(frozen=True)
class Item:
    key: str
    action: str
    rationale: str
    area: str
    min_severity: int
    needs_approval: bool = False
    containment_kind: str | None = None  # matches D's containment action names


def _block(sev):
    return Item("block_sender_domain", "Block the sender and the link domain",
                "This stops more emails from the same sender and blocks the website in the link.",
                "messages", sev, True, "block_sender_domain")


def _quarantine(sev):
    return Item("quarantine_messages", "Quarantine the campaign's messages",
                "Unread copies in other mailboxes can be removed before more people open them.",
                "messages", sev, True, "quarantine")


def _notify(sev, who="the people who received the emails"):
    return Item("notify_users", f"Notify {who}",
                "People who have not clicked yet can ignore the email, and those who did can act early.",
                "notifications", sev, True, "notify_users")


def _report(sev):
    return Item("write_report", "Finish the incident report",
                "A short record of what was detected and done helps management and any later review.",
                "investigation", sev)


TEMPLATES: dict[str, list[Item]] = {
    "credential_phishing": [
        _block(HIGH), _quarantine(HIGH), _notify(HIGH),
        Item("revoke_sessions", "End all signed-in sessions for affected accounts",
             "A password was typed on an unapproved site, so it may be known to others. "
             "Ending sessions cuts off access that is already open.",
             "account", CRITICAL, True, "revoke_sessions"),
        Item("reset_credentials", "Reset the password of affected accounts",
             "Until it is changed, the old password should be treated as exposed.",
             "account", CRITICAL, True, "reset_credentials"),
        Item("review_account_activity", "Review recent sign-in and file activity of affected accounts",
             "We could not verify what happened after the password was entered, so a person should check.",
             "investigation", CRITICAL),
        _report(CRITICAL),
    ],
    "invoice_fraud": [
        Item("confirm_by_phone", "Confirm the bank-detail change by phone, using a number you already have",
             "An email alone cannot prove who asked for the change.", "investigation", MEDIUM),
        Item("hold_payments", "Pause payments to the new bank details until they are confirmed",
             "Payments are hard to recall once they are sent.", "investigation", MEDIUM),
        _quarantine(MEDIUM), _block(MEDIUM), _notify(MEDIUM, "the finance staff who received the emails"),
        _report(MEDIUM),
    ],
    "malware_attachment": [
        _quarantine(MEDIUM), _block(MEDIUM), _notify(MEDIUM),
        Item("scan_devices", "Scan the devices of people who opened the attachment",
             "We cannot tell from the email alone whether the file ran.", "investigation", HIGH),
        _report(MEDIUM),
    ],
    "suspicious_email": [_quarantine(MEDIUM), _block(MEDIUM), _notify(MEDIUM), _report(MEDIUM)],
}

_MONEY_WORDS = ("iban", "bank account", "bank details", "new bank", "invoice", "payment",
                "faktur", "numer konta", "przelew")


def incident_type_for(messages: Iterable[tuple[str, str, list[str]]]) -> str:
    """Keyword heuristic over (subject, body, urls). It only picks which checklist is shown,
    and B's signal categories can replace it. Attachment info is not available here, so
    'malware_attachment' is never chosen automatically."""
    msgs = list(messages)
    if not msgs:
        return "suspicious_email"
    if any(urls for _, _, urls in msgs):
        return "credential_phishing"
    text = " ".join(f"{s} {b}" for s, b, _ in msgs).lower()
    return "invoice_fraud" if any(w in text for w in _MONEY_WORDS) else "suspicious_email"
