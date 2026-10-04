"""LLM helpers for Person C, matching the contract in app/incidents/ai_hooks.py:

    incident_summary(incident: Incident) -> str
    employee_notification(incident: Incident, employee_id: str) -> str
    checklist_reason(incident_type: str, item_key: str, default: str) -> str

Each returns LLM text only when an answer passes the grounding check, else "" (an empty
string, not None: C's hook turns None into the text "None"), so C's own deterministic
template is used and labelled "template", not "llm". Answers come
from the offline cache or the GPU server; the slow laptop model is skipped because an
admin is waiting on these. The LLM never writes steps or counts: those stay deterministic.
"""
from __future__ import annotations

from functools import cache

from app.llm.client import ask
from app.llm.grounding import grounded
from app.llm.prompts import notification_messages, summary_messages

EVIDENCE_WORDS = {
    "email_scored": "a suspicious email was detected",
    "link_clicked": "a link in it was clicked",
    "password_reuse": "a password was typed on an unapproved site",
    "unusual_signin": "an unusual sign-in followed",
    "user_report": "the employee reported what happened",
}
DOMAIN_PREFERENCE = ("password_reuse", "link_clicked", "email_scored")


def _kinds_text(kinds: list[str]) -> str:
    return "; ".join(EVIDENCE_WORDS.get(k, k.replace("_", " ")) for k in kinds)


def _ask_text(messages: list[dict], key: str, max_len: int, facts: list[str]) -> str:
    answer, _ = ask(messages, allow_local=False)
    text = answer.get(key) if answer else None
    if isinstance(text, str) and 0 < len(text.strip()) <= max_len and grounded([text], facts):
        return text.strip()
    return ""


@cache
def _employee_names() -> dict[str, str]:
    try:
        from app.simulation.seed import load_org
        return {e.id: e.name for e in load_org().employees}
    except Exception:  # no org data: fall back to the id
        return {}


def _first_name(employee_id: str) -> str:
    return _employee_names().get(employee_id, employee_id).split()[0]


def checklist_reason(incident_type: str, item_key: str, default: str) -> str:
    """Always "" so C's own rationale is used.

    C's rationales are already written in plain language and are more precise; in testing,
    an LLM rewrite dropped the reason ("typed on an unapproved site") and addressed the
    wrong reader. Kept in the contract so it can be switched on later if wanted.
    """
    return ""


def notification_steps(evidence_kinds: set[str]) -> list[str]:
    """Deterministic, like Assessment.recommended_action: the LLM never writes instructions."""
    steps = ["Do not use the link or reply to the email."]
    if evidence_kinds & {"password_reuse", "unusual_signin"}:
        steps = ["Change your work password now, on the real company sign-in page.",
                 "Do not approve any sign-in prompts you did not start.", *steps]
    return steps + ["Your administrator will follow up."]


def employee_notification(incident, employee_id: str) -> str:
    mine = [e for e in incident.evidence if e.employee_id == employee_id]
    kinds = sorted({e.kind for e in mine})
    if not kinds:
        return ""
    domain = next((e.domain for k in DOMAIN_PREFERENCE for e in mine if e.kind == k and e.domain), None)
    what = _ask_text(notification_messages(incident.type, kinds, domain), "what_happened", 400,
                     [incident.type, _kinds_text(kinds), domain or ""])
    if not what:
        return ""
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(notification_steps(set(kinds)), 1))
    return f"Hi {_first_name(employee_id)},\n{what}\nPlease take these steps now:\n{numbered}"


def incident_summary(incident) -> str:
    kinds = sorted({e.kind for e in incident.evidence})
    story = _ask_text(summary_messages(incident.type, int(incident.severity), kinds), "summary", 500,
                      [incident.type, _kinds_text(kinds)])
    if not story:
        return ""
    # Counts come from C's incident, never from the model.
    names = ", ".join(_employee_names().get(i, i) for i in incident.affected_employees) or "none yet"
    auto = sum(1 for e in incident.evidence if e.source == "automatic")
    done = sum(1 for c in incident.checklist if c.done)
    return (f"{story} Affected employees: {names}. Evidence: {auto} detected automatically, "
            f"{len(incident.evidence) - auto} reported. Checklist: {done} of {len(incident.checklist)} steps done.")
