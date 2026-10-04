"""Person B's checks from INTEGRATION_PLAN.md (B1-B3)."""
import time

import pytest

from app import schemas
from app.detection import message_from_sim
from app.llm import client
from app.ml import download_model
from app.schemas import Severity
from app.scoring import analyze as analyze_module, ml_signal as ml_module
from app.scoring.analyze import analyze
from app.simulation.seed import load_emails

EMAILS = load_emails()
AMBIGUOUS = "amb-01"


def expected(sim) -> Severity:
    if sim.id == AMBIGUOUS:
        return Severity.MEDIUM
    return Severity.HIGH if sim.scenario.label == "phishing" else Severity.LOW


# B1: analyze() returns the shared Assessment from schemas.py
def test_b1_analyze_returns_the_shared_assessment():
    a = analyze(message_from_sim(EMAILS[0]), use_ml=False)
    assert type(a) is schemas.Assessment
    assert schemas.Assessment.model_validate_json(a.model_dump_json()) == a


def test_b1_ambiguous_email_is_medium_with_a_stated_uncertainty():
    a = analyze(message_from_sim(next(e for e in EMAILS if e.id == AMBIGUOUS)), use_ml=False)
    assert a.risk == Severity.MEDIUM
    assert a.uncertainties, "the plan asks for MEDIUM *with a stated uncertainty*"


# B2: the shipped weights load fast and score the demo correctly
@pytest.mark.skipif(not download_model.is_valid(), reason="weights not installed: python -m app.ml.download_model")
def test_b2_distilbert_loads_under_two_seconds():
    pytest.importorskip("transformers")
    from app.ml.transformer_model import PhishingTransformer
    start = time.perf_counter()
    PhishingTransformer.load()
    assert time.perf_counter() - start < 2.0


def test_b2_tfidf_fallback_never_lifts_legit_mail(monkeypatch):
    """Teammates without torch get the TF-IDF fallback; the demo verdicts must not change."""
    pytest.importorskip("sklearn")
    monkeypatch.setattr("app.ml.transformer_model.PhishingTransformer.load",
                        classmethod(lambda cls, *a, **k: (_ for _ in ()).throw(RuntimeError("no weights"))),
                        raising=False)
    classifier = ml_module._Classifier()
    assert classifier.name == ml_module.FALLBACK
    monkeypatch.setattr(analyze_module, "classify", classifier.score)
    wrong = {e.id: r for e in EMAILS if (r := analyze(message_from_sim(e)).risk) != expected(e)}
    assert not wrong, wrong


# B3: with the LLM off and no cache, every demo email still gets a full explanation
def test_b3_template_fallback_covers_every_demo_email(monkeypatch):
    monkeypatch.setattr(client, "_cached", lambda: {})
    monkeypatch.setenv("LLM_LIVE", "0")
    for sim in EMAILS:
        a = analyze(message_from_sim(sim), use_ml=False)
        assert a.explanation.source == "template"
        assert a.explanation.summary and a.recommended_action
        assert a.risk == expected(sim), sim.id
