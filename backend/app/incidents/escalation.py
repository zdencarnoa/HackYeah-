"""Escalation rules: one table, easy to explain in the pitch.

The system recommends, the admin approves. Employee reports confirm or raise
severity but are never required.
"""
from __future__ import annotations

from app.schemas import Evidence, Severity
from app.simulation.seed import load_approved_logins

# The company's real sign-in domains (D's ApprovedLogins). A password typed on any
# domain outside this set is treated as reuse on a phishing site.
APPROVED_LOGINS = {login.domain for login in load_approved_logins()}

_REPORT_SEVERITY = {
    "password": Severity.CRITICAL,
    "clicked": Severity.HIGH,
    "downloaded": Severity.HIGH,
    "other_info": Severity.HIGH,
    # "none" -> no incident
}


def severity_for(ev: Evidence) -> Severity | None:
    """None means: store the evidence, but it does not open or raise an incident."""
    if ev.kind == "link_clicked":
        return Severity.HIGH  # possible exposure
    if ev.kind in ("password_reuse", "unusual_signin"):
        return Severity.CRITICAL  # likely compromise
    if ev.kind == "user_report":
        return _REPORT_SEVERITY.get(ev.interaction_kind or "")
    return None  # email_scored: campaign watch only


def describe(ev: Evidence) -> str:
    """Plain-language timeline text. States what was observed, nothing more."""
    if ev.kind == "email_scored":
        return "A suspicious email was delivered"
    if ev.kind == "link_clicked":
        return "A link in a suspicious email was clicked (possible exposure)"
    if ev.kind == "password_reuse":
        return f"A password was typed on an unapproved site ({ev.domain or 'unknown domain'})"
    if ev.kind == "unusual_signin":
        return "An unusual sign-in was seen shortly after the click"
    reported = {
        "password": "The employee reported entering their password",
        "clicked": "The employee reported clicking a link",
        "downloaded": "The employee reported downloading an attachment",
        "other_info": "The employee reported entering other information",
    }
    return reported.get(ev.interaction_kind or "", "The employee sent a report")


GUIDANCE = {
    "none": ["Do not click anything in this email.", "Delete it or forward it to your admin."],
    "clicked": [
        "Do not enter any information on the page you opened.",
        "Close the page and tell your admin that you clicked.",
        "Watch for unexpected sign-in or password-reset messages.",
    ],
    "downloaded": [
        "Do not open the file. Leave it where it is.",
        "Tell your admin so the file can be checked.",
    ],
    "password": [
        "Change your password now, from the real company sign-in page.",
        "Tell your admin. They can end other sessions on your account.",
        "If you reuse this password elsewhere, change it there too.",
    ],
    "other_info": [
        "Tell your admin what information you entered.",
        "If it was a card or bank detail, contact your bank.",
    ],
}
