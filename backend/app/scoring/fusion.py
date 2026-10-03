"""Risk fusion: signals (rules + ML) -> one risk level, by a transparent rule table.

1. Points: per signal category, only the strongest signal counts (three suspicious
   URLs are one problem, not three), weighted by severity.
2. Level from points.
3. Floors: combinations that are phishing on their own (a credential request from an
   impersonated sender, a known-bad indicator, ...) are at least HIGH.
4. Cap: HIGH needs at least one moderate rule-based signal; ML and weak signals alone
   stay at MEDIUM or below.
5. An email on its own is at most HIGH. CRITICAL needs evidence of compromise
   (click + password, unusual sign-in), which Person C's escalation adds.

Missing checks never add points; they become uncertainties.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas import Signal, SignalCategory as C
from app.schemas_proposal_b import Severity

WEIGHT = {0: 0, 1: 1, 2: 3, 3: 6}  # signal severity -> points
MEDIUM_AT, HIGH_AT = 3, 6

IMPERSONATION = {C.BRAND_IMPERSONATION, C.COLLEAGUE_IMPERSONATION, C.FREEMAIL_IMPERSONATION, C.LOOKALIKE_DOMAIN}

# (name, condition on {category: strongest severity}) -> at least HIGH
FLOORS: list[tuple[str, callable]] = [
    ("credential request from an impersonated sender",
     lambda s: s.get(C.CREDENTIAL_REQUEST, 0) >= 2 and any(s.get(c, 0) >= 2 for c in IMPERSONATION)),
    ("known malicious indicator", lambda s: s.get(C.KNOWN_BAD, 0) >= 3),
    ("request for an MFA code or approval", lambda s: s.get(C.MFA_CODE_REQUEST, 0) >= 3),
    ("gift card request from an impersonated colleague",
     lambda s: s.get(C.GIFT_CARD, 0) >= 2 and s.get(C.COLLEAGUE_IMPERSONATION, 0) >= 2),
    ("payment change with a mismatched or impersonated sender",
     lambda s: s.get(C.PAYMENT_CHANGE, 0) >= 2 and any(
         s.get(c, 0) >= 2 for c in IMPERSONATION | {C.REPLY_TO_MISMATCH, C.RETURN_PATH_MISMATCH})),
]


@dataclass
class FusionResult:
    risk: Severity
    score: int
    signals: list[Signal]  # deduplicated input, strongest first
    rules_fired: list[str] = field(default_factory=list)  # for "Advanced details" and tests


def strongest_by_category(signals: list[Signal]) -> dict[C, int]:
    out: dict[C, int] = {}
    for s in signals:
        out[s.category] = max(out.get(s.category, 0), s.severity)
    return out


def fuse(signals: list[Signal]) -> FusionResult:
    strongest = strongest_by_category(signals)
    score = sum(WEIGHT[sev] for sev in strongest.values())
    rules = []

    risk = Severity.HIGH if score >= HIGH_AT else Severity.MEDIUM if score >= MEDIUM_AT else Severity.LOW

    for name, condition in FLOORS:
        if condition(strongest):
            rules.append(f"floor: {name}")
            risk = max(risk, Severity.HIGH)

    has_moderate_rule = any(s.severity >= 2 and s.source != "ml" for s in signals)
    if risk >= Severity.HIGH and not has_moderate_rule:
        rules.append("cap: no moderate rule-based signal, ML and weak signals alone stay at MEDIUM")
        risk = Severity.MEDIUM

    ordered = sorted(signals, key=lambda s: (-s.severity, s.source == "ml", s.category, s.id))
    return FusionResult(risk=Severity(risk), score=score, signals=ordered, rules_fired=rules)
