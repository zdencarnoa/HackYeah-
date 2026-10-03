"""LLM helpers for Person C: employee notification, incident summary, checklist rationale.

Each returns text from the cache or a live LLM when that answer passes the grounding
check, else a deterministic template. C passes plain values, so these do not depend
on the final Incident schema.
"""
from __future__ import annotations

from app.llm.client import ask
from app.llm.grounding import grounded
from app.llm.prompts import notification_messages, rationale_messages, summary_messages
from app.schemas_proposal_b import Severity

EVIDENCE_WORDS = {
    "email_scored": "a suspicious email was detected",
    "link_clicked": "a link in it was clicked",
    "password_reuse": "a password was typed on an unapproved site",
    "unusual_signin": "an unusual sign-in followed",
    "user_report": "the employee reported what happened",
}

# Rationale per checklist action (C's templated checklists use these action texts).
RATIONALE = {
    "Revoke active sessions": "If the password was captured, revoking sessions stops an attacker who may already be signed in.",
    "Reset credentials": "A new password makes the captured one useless.",
    "Verify MFA configuration": "Attackers sometimes add their own sign-in method; checking MFA removes that backdoor.",
    "Search for related messages": "Phishing usually arrives in waves, so other employees may have the same email.",
    "Notify affected users": "People who know about the attack are far less likely to fall for the next email.",
    "Monitor account activity": "Unusual activity in the next days can show whether the account was misused.",
    "Document incident": "A written record helps the follow-up review and any reporting duties.",
    "Quarantine messages": "Removing the emails from inboxes prevents further clicks.",
    "Block sender": "Blocking the sender stops new messages from the same address.",
    "Block domain": "Blocking the domain stops messages and links from the attacker's infrastructure.",
    "Confirm payment details by phone": "A call to a known number is the surest way to catch a fake bank-detail change.",
    "Hold pending payments": "Pausing the payment keeps money from going to an account the attacker controls.",
    "Isolate the device": "Disconnecting the device stops malware from spreading or sending data out.",
}
DEFAULT_RATIONALE = "This step limits the possible damage while the incident is investigated."


def _kinds_text(kinds: list[str]) -> str:
    return "; ".join(EVIDENCE_WORDS.get(k, k.replace("_", " ")) for k in kinds)


def checklist_rationale(action: str, incident_type: str) -> str:
    messages = rationale_messages(action, incident_type)
    answer, _ = ask(messages)
    text = answer.get("rationale") if answer else None
    if isinstance(text, str) and 0 < len(text) <= 250 and grounded([text], [action, incident_type]):
        return text.strip()
    return RATIONALE.get(action, DEFAULT_RATIONALE)


def _llm_text(answer: dict | None, key: str, max_len: int, facts: list[str]) -> str | None:
    text = answer.get(key) if answer else None
    if isinstance(text, str) and 0 < len(text.strip()) <= max_len and grounded([text], facts):
        return text.strip()
    return None


def notification_steps(evidence_kinds: list[str]) -> list[str]:
    """Deterministic, like Assessment.recommended_action: the LLM never writes instructions."""
    steps = ["Do not use the link or reply to the email."]
    if "password_reuse" in evidence_kinds:
        steps = ["Change your work password now, on the real company sign-in page.",
                 "Do not approve any sign-in prompts you did not start.", *steps]
    return steps + ["Your administrator will follow up."]


def employee_notification(name: str, incident_type: str, evidence_kinds: list[str], domain: str | None = None) -> str:
    kinds = sorted(set(evidence_kinds))
    answer, _ = ask(notification_messages(incident_type, kinds, domain))
    what = _llm_text(answer, "what_happened", 400, [incident_type, _kinds_text(kinds), domain or ""])
    if what is None:
        where = f" on {domain}" if domain else ""
        what = f"We detected a security issue connected to your account{where}: {_kinds_text(kinds)}."
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(notification_steps(kinds), 1))
    return f"Hi {name},\n{what}\nPlease take these steps now:\n{numbered}"


def incident_summary(incident_type: str, severity: Severity, evidence_kinds: list[str], *, messages: int,
                     recipients: int, departments: int, employee: str) -> str:
    kinds = sorted(set(evidence_kinds))
    answer, _ = ask(summary_messages(incident_type, int(severity), kinds))
    story = _llm_text(answer, "summary", 500, [incident_type, _kinds_text(kinds)])
    if story is None:
        story = (f"{severity.name.title()} {incident_type.replace('_', ' ')} incident. "
                 f"Evidence so far: {_kinds_text(kinds)}.")
    # Counts are facts from C's data, never generated.
    return (f"{story} Scope: {messages} messages, {recipients} recipients, {departments} departments; "
            f"most affected employee: {employee}.")
