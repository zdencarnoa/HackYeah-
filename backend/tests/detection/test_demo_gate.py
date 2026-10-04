"""The demo gate: what the live demo relies on, end to end through detect()."""

import re
import time
from email import message_from_bytes, policy

import pytest

from app.detection import detect, message_from_sim, parse_eml, render_eml
from app.schemas import SignalCategory
from app.simulation.seed import load_emails

EMAILS = load_emails()
CAMPAIGN = [sim for sim in EMAILS if sim.scenario.campaign_id == "camp-ms-verify"]
# amb-01 is deliberately ambiguous (MEDIUM), so it is not held to the "no strong signal" bar.
LEGIT = [sim for sim in EMAILS if sim.scenario.label == "legitimate" and sim.id != "amb-01"]
PHISHING = [sim for sim in EMAILS if sim.scenario.label == "phishing"]
FIVE = {SignalCategory.LOOKALIKE_DOMAIN, SignalCategory.URGENCY, SignalCategory.CREDENTIAL_REQUEST,
        SignalCategory.SUSPICIOUS_URL, SignalCategory.BRAND_IMPERSONATION}
# Words that belong in technical_detail, never in what an employee reads.
JARGON_RE = re.compile(r"\b(spf|dkim|dmarc|punycode|homoglyph|levenshtein|registrable|idn|xn--\S*)\b",
                       re.IGNORECASE)


def by_id(sim):
    return sim.id


def test_dataset_is_present():  # an empty dataset would silently skip everything below
    assert len(CAMPAIGN) == 14 and len(LEGIT) >= 10


@pytest.mark.parametrize("sim", CAMPAIGN, ids=by_id)
def test_microsoft_variant_fires_all_five_indicators(sim):
    categories = {s.category for s in detect(message_from_sim(sim)).signals}
    assert FIVE <= categories, f"missing: {sorted(FIVE - categories)}"


@pytest.mark.parametrize("sim", CAMPAIGN, ids=by_id)
def test_five_indicators_do_not_need_authentication_headers(sim):
    msg = message_from_bytes(render_eml(sim), policy=policy.default)
    del msg["Authentication-Results"]
    categories = {s.category for s in detect(parse_eml(msg.as_bytes())).signals}
    assert FIVE <= categories, f"missing: {sorted(FIVE - categories)}"


@pytest.mark.parametrize("sim", LEGIT, ids=by_id)
def test_legitimate_email_has_no_strong_signal(sim):
    signals = detect(message_from_sim(sim)).signals
    assert all(s.severity < 2 for s in signals), [(s.id, s.evidence) for s in signals]


@pytest.mark.parametrize("sim", PHISHING, ids=by_id)
def test_every_phishing_email_has_a_strong_signal(sim):
    signals = detect(message_from_sim(sim)).signals
    assert any(s.severity >= 2 for s in signals), [(s.id, s.severity) for s in signals]


@pytest.mark.parametrize("sim", EMAILS, ids=by_id)
def test_evidence_is_short_plain_language(sim):
    for signal in detect(message_from_sim(sim)).signals:
        assert not JARGON_RE.search(signal.evidence), (signal.id, signal.evidence)
        assert len(signal.evidence.split()) <= 45, (signal.id, signal.evidence)


def test_detect_is_deterministic():
    for sim in EMAILS:
        message = message_from_sim(sim)
        assert detect(message) == detect(message), sim.id


def test_parse_and_detect_take_well_under_100_ms():
    raws = [render_eml(sim) for sim in EMAILS]
    start = time.perf_counter()
    for raw in raws:
        detect(parse_eml(raw))
    per_email_ms = 1000 * (time.perf_counter() - start) / len(raws)
    assert per_email_ms < 100, per_email_ms


def test_ambiguous_email_is_medium_with_a_dmarc_note():
    message = message_from_sim(next(sim for sim in EMAILS if sim.id == "amb-01"))
    result = detect(message)
    severities = {s.id: s.severity for s in result.signals}
    assert severities["content.credential_request"] == 2
    assert severities["url.foreign_domain"] == 1
    assert max(severities.values()) == 2
    assert any("DMARC" in note for note in result.unchecked)
