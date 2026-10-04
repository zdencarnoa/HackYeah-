"""analyze(): Message -> Assessment. A's signals + ML + fusion + explanation."""
from __future__ import annotations

from app.detection import detect
from app.schemas import Message
from app.schemas import Assessment
from app.scoring.fusion import fuse
from app.scoring.ml_signal import classify, ml_signal
from app.llm.explain import explain_assessment
from app.scoring.templates import recommended_action

UNSURE_LOW, UNSURE_HIGH = 0.35, 0.65


def analyze(message: Message, use_ml: bool = True) -> Assessment:
    detection = detect(message)
    uncertainties = list(detection.unchecked)

    ml = classify(message) if use_ml else None
    if ml is None:
        uncertainties.append("We could not run the text classifier, so the wording was not analysed.")
    elif UNSURE_LOW <= ml.probability <= UNSURE_HIGH:
        uncertainties.append("Our text classifier is unsure about the wording of this email; "
                             "this does not prove it is safe or malicious.")

    signals = list(detection.signals)
    if (sig := ml_signal(ml)) is not None:
        signals.append(sig)

    result = fuse(signals)
    return Assessment(
        message_id=message.id,
        risk=result.risk,
        score=result.score,
        signals=result.signals,
        ml_confidence=round(ml.probability, 4) if ml else None,
        ml_model=ml.model if ml else None,
        uncertainties=uncertainties,
        explanation=explain_assessment(result.risk, result.signals, uncertainties),
        recommended_action=recommended_action(result.risk, result.signals),
    )
