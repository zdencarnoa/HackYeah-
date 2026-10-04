"""LLM explanation of an Assessment, grounded in its evidence, with the template as fallback.

The LLM rewrites the evidence for a non-expert; it never sees the email, never sets
the risk level and never writes the recommended action (that stays deterministic).
"""
from __future__ import annotations

from app.llm.client import ask
from app.llm.grounding import grounded, short_strings
from app.llm.prompts import explanation_messages
from app.schemas import Signal
from app.schemas import Explanation, Severity
from app.scoring.templates import MAX_REASONS, SUMMARY, reasons

# ML uncertainties depend on which model a laptop has; keep them out of the prompt so
# the cached answer matches on every machine (they still show in Assessment.uncertainties).
ML_UNCERTAINTY_PREFIXES = ("Our text classifier", "We could not run the text classifier")


def llm_inputs(risk: Severity, signals: list[Signal], uncertainties: list[str]) -> tuple[list[str], list[str]]:
    evidence = reasons([s for s in signals if s.source != "ml"])
    unsure = [u for u in uncertainties if not u.startswith(ML_UNCERTAINTY_PREFIXES)]
    return evidence, unsure


def explain_assessment(risk: Severity, signals: list[Signal], uncertainties: list[str],
                       live: bool = True) -> Explanation:
    evidence, unsure = llm_inputs(risk, signals, uncertainties)
    answer, _ = ask(explanation_messages(int(risk), evidence, unsure), live=live)
    ml_reasons = reasons([s for s in signals if s.source == "ml"])

    if answer is not None:
        summary = answer.get("summary")
        llm_reasons = short_strings(answer.get("reasons", []), max_items=4, max_len=300)
        if (isinstance(summary, str) and 0 < len(summary) <= 300 and llm_reasons is not None
                and (evidence or not llm_reasons)
                and grounded([summary, *llm_reasons], evidence + unsure)):
            return Explanation(summary=summary.strip(), reasons=(llm_reasons + ml_reasons)[:MAX_REASONS],
                               source="llm")

    return Explanation(summary=SUMMARY[risk], reasons=reasons(signals), source="template")
