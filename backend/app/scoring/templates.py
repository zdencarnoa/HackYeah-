"""Deterministic explanations: the fallback when the LLM is slow or offline.

Built only from evidence already in the signals (Person A writes each Signal.evidence
as a plain-language sentence), so nothing is invented.
"""
from __future__ import annotations

from app.schemas import Signal, SignalCategory as C
from app.schemas_proposal_b import Explanation, Severity

MAX_REASONS = 5

SUMMARY = {
    Severity.LOW: "We found no warning signs in this email.",
    Severity.MEDIUM: "This email has some warning signs. It may be legitimate, but be careful.",
    Severity.HIGH: "This email is very likely a phishing attempt.",
    Severity.CRITICAL: "This email is part of an active attack that may already have compromised an account.",
}

BASE_ACTION = {
    Severity.LOW: "No action is needed. If something still feels off, report the message.",
    Severity.MEDIUM: "Before clicking links or replying, confirm the request through another channel you trust.",
    Severity.HIGH: "Do not click any links, open attachments or reply. Report the message.",
    Severity.CRITICAL: "Do not interact with this email. Report it now and follow your administrator's instructions.",
}

# Specific advice for HIGH and above, strongest concern first.
SPECIFIC_ACTION = [
    (C.CREDENTIAL_REQUEST, "Do not enter your password. If you need the service, open it directly, not through the link."),
    (C.MFA_CODE_REQUEST, "Never approve unexpected sign-in prompts or share verification codes."),
    (C.PAYMENT_CHANGE, "Do not change any payment details. Confirm by phone using a number you already know."),
    (C.GIFT_CARD, "Do not buy gift cards. Check with the person directly, not by replying."),
    (C.RISKY_ATTACHMENT, "Do not open the attachment."),
]


def reasons(signals: list[Signal]) -> list[str]:
    """One sentence per category (its strongest signal), strongest first."""
    seen, out = set(), []
    for s in signals:  # already sorted strongest first by fusion
        if s.severity == 0 or s.category in seen:
            continue
        seen.add(s.category)
        out.append(s.evidence)
    return out[:MAX_REASONS]


def recommended_action(risk: Severity, signals: list[Signal]) -> str:
    if risk < Severity.HIGH:
        return BASE_ACTION[risk]
    categories = {s.category for s in signals if s.severity >= 2}
    specific = [text for cat, text in SPECIFIC_ACTION if cat in categories]
    return " ".join(specific[:2] + [BASE_ACTION[risk]])


def explain(risk: Severity, signals: list[Signal]) -> Explanation:
    return Explanation(summary=SUMMARY[risk], reasons=reasons(signals), source="template")
