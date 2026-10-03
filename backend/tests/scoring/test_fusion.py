import pytest

from app.schemas import Signal, SignalCategory as C
from app.schemas_proposal_b import Severity
from app.scoring.fusion import fuse
from app.scoring.ml_signal import MlResult, ml_signal
from app.scoring.templates import explain, recommended_action


def sig(category, severity, source="rule", rule_id=None):
    return Signal(id=rule_id or f"{category}.{severity}", category=category, severity=severity,
                  evidence=f"evidence for {category}", technical_detail="-", source=source)


def ml(p):
    return ml_signal(MlResult(p, "test"))


def test_no_signals_is_low():
    assert fuse([]).risk == Severity.LOW


@pytest.mark.parametrize("p", [0.6, 0.9, 0.999])
def test_ml_alone_never_reaches_high(p):
    assert fuse([ml(p)]).risk <= Severity.MEDIUM


def test_ml_below_threshold_is_not_evidence():
    assert ml(0.59) is None
    assert ml(0.6).severity == 1
    assert ml(0.95).severity == 2


def test_ml_plus_weak_signals_stays_medium():
    signals = [ml(0.99), sig(C.AUTH_FAILURE, 1), sig(C.SUSPICIOUS_URL, 1), sig(C.RETURN_PATH_MISMATCH, 1)]
    result = fuse(signals)
    assert result.risk == Severity.MEDIUM
    assert any(r.startswith("cap") for r in result.rules_fired)


def test_one_moderate_signal_is_medium():
    assert fuse([sig(C.URGENCY, 2)]).risk == Severity.MEDIUM


def test_one_strong_rule_signal_is_high():
    assert fuse([sig(C.LOOKALIKE_DOMAIN, 3)]).risk == Severity.HIGH


def test_same_category_counts_once():
    once = fuse([sig(C.SUSPICIOUS_URL, 2, rule_id="url.a")])
    thrice = fuse([sig(C.SUSPICIOUS_URL, 2, rule_id=f"url.{i}") for i in "abc"])
    assert once.score == thrice.score


@pytest.mark.parametrize("signals", [
    [sig(C.CREDENTIAL_REQUEST, 2), sig(C.COLLEAGUE_IMPERSONATION, 2)],
    [sig(C.KNOWN_BAD, 3)],
    [sig(C.MFA_CODE_REQUEST, 3)],
    [sig(C.GIFT_CARD, 2), sig(C.COLLEAGUE_IMPERSONATION, 2)],
    [sig(C.PAYMENT_CHANGE, 2), sig(C.REPLY_TO_MISMATCH, 2)],
], ids=["credential+impersonation", "known_bad", "mfa", "gift_card", "payment_change"])
def test_floors_force_at_least_high(signals):
    assert fuse(signals).risk >= Severity.HIGH


def test_an_email_alone_is_never_critical():
    everything = [sig(c, 3) for c in C if c != C.ML_PHISHING] + [ml(0.999)]
    assert fuse(everything).risk == Severity.HIGH


def test_reasons_are_evidence_strongest_first_one_per_category():
    result = fuse([sig(C.URGENCY, 2), sig(C.LOOKALIKE_DOMAIN, 3), sig(C.SUSPICIOUS_URL, 1, rule_id="u1"),
                   sig(C.SUSPICIOUS_URL, 3, rule_id="u2")])
    reasons = explain(result.risk, result.signals).reasons
    assert reasons[0].endswith(("lookalike_domain", "suspicious_url"))
    assert len(reasons) == len(set(reasons)) == 3


def test_high_action_is_specific():
    result = fuse([sig(C.CREDENTIAL_REQUEST, 2), sig(C.LOOKALIKE_DOMAIN, 3)])
    action = recommended_action(result.risk, result.signals)
    assert "password" in action and "Report" in action
