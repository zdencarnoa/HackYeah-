"""Hooks for Person B's LLM helpers, each with a deterministic offline fallback.

Contract with B: create backend/app/llm/helpers.py with any of these functions.
  incident_summary(incident: Incident) -> str
  employee_notification(incident: Incident, employee_id: str) -> str
  checklist_reason(incident_type: str, item_key: str, default: str) -> str
Missing module, missing function, an exception: we fall back to the template, so the demo never
depends on the network. B's functions should enforce their own short timeout.
They receive structured evidence only, never raw email text.
"""
from __future__ import annotations

from app.schemas_proposal import Incident, Severity


def _helpers():
    try:
        from app.llm import helpers  # Person B's module
        return helpers
    except Exception:  # not written yet, or failed to import
        return None


def _try(name: str, *args) -> str | None:
    h = _helpers()
    fn = getattr(h, name, None) if h else None
    if fn is None:
        return None
    try:
        out = fn(*args)
        return str(out).strip() or None
    except Exception:
        return None


def checklist_reason(incident_type: str, item_key: str, default: str) -> str:
    return _try("checklist_reason", incident_type, item_key, default) or default


def incident_summary(inc: Incident) -> tuple[str, str]:
    text = _try("incident_summary", inc)
    if text:
        return text, "llm"
    auto = sum(1 for e in inc.evidence if e.source == "automatic")
    reported = len(inc.evidence) - auto
    done = sum(1 for c in inc.checklist if c.done)
    who = ", ".join(inc.affected_employees) or "none yet"
    return (
        f"{inc.type.replace('_', ' ').capitalize()} incident, severity {Severity(inc.severity).name}. "
        f"Affected employees: {who}. {auto} evidence item(s) were detected automatically and "
        f"{reported} were reported by employees. Response checklist: {done} of {len(inc.checklist)} "
        "steps done. This summary lists what was observed; it does not prove what an attacker did."
    ), "template"


def employee_notification(inc: Incident, employee_id: str) -> tuple[str, str]:
    text = _try("employee_notification", inc, employee_id)
    if text:
        return text, "llm"
    kinds = {e.kind for e in inc.evidence if e.employee_id == employee_id}
    reports = {e.interaction_kind for e in inc.evidence
               if e.employee_id == employee_id and e.kind == "user_report"}
    lines = ["Our security system flagged a suspicious email sent to you."]
    if "link_clicked" in kinds:
        lines.append("We noticed that a link in that email was clicked.")
    if "password_reuse" in kinds:
        lines.append("We noticed your password was typed on a site that is not on the approved sign-in list.")
    if "unusual_signin" in kinds:
        lines.append("We also saw a sign-in to your account from an unusual location.")
    if kinds & {"password_reuse", "unusual_signin"} or "password" in reports:
        lines.append("Please change your password from the real company sign-in page and tell your admin.")
    else:
        lines.append("Please do not click links in it, and delete it or forward it to your admin.")
    lines.append("This is guidance based on what was detected. It does not mean your account was misused.")
    return " ".join(lines), "template"
