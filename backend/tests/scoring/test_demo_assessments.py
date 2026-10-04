"""The demo-critical outputs from the team plan, on Person D's demo emails.

Rules alone (checkpoint 2: "HIGH from the rules alone") and, when a model is
available, with ML switched on.
"""
import pytest

from app.detection import message_from_sim
from app.schemas import Severity
from app.scoring.analyze import analyze
from app.scoring.ml_signal import classify
from app.simulation.seed import load_emails

EMAILS = load_emails()
PHISHING = [e for e in EMAILS if e.scenario.label == "phishing"]
LEGIT = [e for e in EMAILS if e.scenario.label == "legitimate"]
MICROSOFT = [e for e in PHISHING if e.scenario.campaign_id == "camp-ms-verify"]


def _ml_available():
    return classify(message_from_sim(EMAILS[0])) is not None


@pytest.mark.parametrize("use_ml", [False, True])
def test_legitimate_demo_emails_are_low(use_ml):
    if use_ml and not _ml_available():
        pytest.skip("no ML model installed")
    risks = {e.subject: analyze(message_from_sim(e), use_ml=use_ml).risk for e in LEGIT}
    assert all(r == Severity.LOW for r in risks.values()), risks


@pytest.mark.parametrize("use_ml", [False, True])
def test_phishing_demo_emails_are_high(use_ml):
    if use_ml and not _ml_available():
        pytest.skip("no ML model installed")
    risks = {e.subject: analyze(message_from_sim(e), use_ml=use_ml).risk for e in PHISHING}
    assert all(r == Severity.HIGH for r in risks.values()), risks


def test_microsoft_campaign_is_there_and_high():
    assert len(MICROSOFT) == 14
    a = analyze(message_from_sim(MICROSOFT[0]), use_ml=False)
    assert a.risk == Severity.HIGH
    assert "password" in a.recommended_action
    assert len(a.explanation.reasons) >= 3


def test_without_ml_the_gap_is_stated_not_counted():
    a = analyze(message_from_sim(LEGIT[0]), use_ml=False)
    assert a.ml_confidence is None
    assert any("text classifier" in u for u in a.uncertainties)
    assert a.risk == Severity.LOW
