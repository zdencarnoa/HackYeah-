"""The ML classifier as one more signal for risk fusion.

Loads the best model available, once: DistilBERT (needs torch + transformers and
the weights from the model-v1 release), else the TF-IDF fallback (needs
scikit-learn), else none. A missing model is reported as an uncertainty and is
never counted as evidence.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.ml.text import email_text, normalize
from app.schemas import Message, Signal, SignalCategory

log = logging.getLogger(__name__)

ML_DIR = Path(__file__).resolve().parent.parent / "ml" / "models"
# Probability -> signal severity. Capped at 2 so the model alone can never reach HIGH.
STRONG, MODERATE = 0.90, 0.60


@dataclass(frozen=True)
class MlResult:
    probability: float  # calibrated phishing probability 0-1
    model: str  # "distilbert-v1" or "tfidf-fallback"


class _Classifier:
    def __init__(self):
        self.name, self._predict = self._load()

    @staticmethod
    def _load():
        try:
            from app.ml.transformer_model import PhishingTransformer
            model = PhishingTransformer.load()
            return "distilbert-v1", lambda text: model.predict_proba([text])[0]
        except Exception as exc:  # missing weights or torch: fall back, never crash the demo
            log.warning("DistilBERT unavailable (%s); trying TF-IDF fallback", exc)
        try:
            import joblib
            pipeline = joblib.load(ML_DIR / "baseline.joblib")["pipeline"]
            return "tfidf-fallback", lambda text: float(pipeline.predict_proba([normalize(text)])[0, 1])
        except Exception as exc:
            log.warning("TF-IDF fallback unavailable (%s); scoring without ML", exc)
        return None, None

    def score(self, message: Message) -> MlResult | None:
        if self._predict is None:
            return None
        return MlResult(float(self._predict(email_text(message.subject, message.body_text))), self.name)


_classifier: _Classifier | None = None


def classify(message: Message) -> MlResult | None:
    """Phishing probability for the message text, or None when no model can be loaded."""
    global _classifier
    if _classifier is None:
        _classifier = _Classifier()
    return _classifier.score(message)


def ml_signal(result: MlResult | None) -> Signal | None:
    """Turn the probability into a Signal; below MODERATE the text alone is not evidence."""
    if result is None or result.probability < MODERATE:
        return None
    pct = round(result.probability * 100)
    if result.probability >= STRONG:
        severity, evidence = 2, "The wording of this email closely matches known phishing emails."
    else:
        severity, evidence = 1, "Parts of the wording resemble phishing emails."
    return Signal(id="ml.text", category=SignalCategory.ML_PHISHING, severity=severity, evidence=evidence,
                  technical_detail=f"text classifier {result.model}: p(phishing) = {pct}%", source="ml")
