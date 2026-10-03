import pytest

from app.llm import client, explain as explain_module, helpers
from app.llm.grounding import grounded
from app.llm.prompts import explanation_messages, fingerprint
from app.schemas import Signal, SignalCategory as C
from app.schemas_proposal_b import Severity
from app.scoring.fusion import fuse

EVIDENCE = "The sender's domain micr0soft-example.test imitates Microsoft."


def signals():
    return fuse([Signal(id="d.lookalike", category=C.LOOKALIKE_DOMAIN, severity=3, evidence=EVIDENCE,
                        technical_detail="-", source="rule")]).signals


@pytest.fixture(autouse=True)
def no_cache_no_live(monkeypatch):
    monkeypatch.setattr(client, "_cached", lambda: {})
    monkeypatch.delenv("LLM_BASE_URL", raising=False)


def answer_with(monkeypatch, answer):
    monkeypatch.setattr(explain_module, "ask", lambda messages: (answer, "cache"))
    monkeypatch.setattr(helpers, "ask", lambda messages: (answer, "cache"))


def test_grounding_rejects_invented_domains_and_numbers():
    assert grounded(["It imitates micr0soft-example.test."], [EVIDENCE])
    assert not grounded(["Go to evil-site.example instead."], [EVIDENCE])
    assert not grounded(["97% of such emails are phishing."], [EVIDENCE])


def test_without_llm_the_template_explains():
    e = explain_module.explain_assessment(Severity.HIGH, signals(), [])
    assert e.source == "template" and e.reasons == [EVIDENCE]


def test_cached_answer_is_used_when_grounded(monkeypatch):
    answer_with(monkeypatch, {"summary": "This is very likely phishing.",
                              "reasons": ["The address micr0soft-example.test only pretends to be Microsoft."]})
    e = explain_module.explain_assessment(Severity.HIGH, signals(), [])
    assert e.source == "llm" and "micr0soft-example.test" in e.reasons[0]


@pytest.mark.parametrize("bad", [
    {"summary": "Phishing.", "reasons": ["It links to steal-passwords.example."]},  # invented domain
    {"summary": "Phishing.", "reasons": "not a list"},
    {"summary": "", "reasons": []},
    {"reasons": ["x"]},
])
def test_bad_answers_fall_back_to_template(monkeypatch, bad):
    answer_with(monkeypatch, bad)
    assert explain_module.explain_assessment(Severity.HIGH, signals(), []).source == "template"


def test_cache_lookup_uses_the_exact_prompt(monkeypatch):
    messages = explanation_messages(2, [EVIDENCE], [])
    monkeypatch.setattr(client, "_cached", lambda: {fingerprint(messages): {"summary": "ok"}})
    assert client.ask(messages) == ({"summary": "ok"}, "cache")
    assert client.ask(explanation_messages(1, [EVIDENCE], [])) == (None, None)


def test_helpers_fall_back_to_templates():
    note = helpers.employee_notification("Alice", "credential_phishing", ["email_scored", "password_reuse"],
                                         "login.micr0soft-example.test")
    assert note.startswith("Hi Alice") and "Change your work password" in note
    assert helpers.checklist_rationale("Revoke active sessions", "credential_phishing") == \
        helpers.RATIONALE["Revoke active sessions"]
    summary = helpers.incident_summary("credential_phishing", Severity.CRITICAL, ["password_reuse"],
                                       messages=14, recipients=7, departments=3, employee="Alice")
    assert "14 messages" in summary and "7 recipients" in summary


def test_llm_writes_the_story_but_steps_and_counts_stay_deterministic(monkeypatch):
    answer_with(monkeypatch, {"what_happened": "Your password was typed on a fake sign-in page.",
                              "summary": "A credential phishing attack reached the stage of a stolen password."})
    note = helpers.employee_notification("Alice", "credential_phishing", ["password_reuse"])
    assert note.startswith("Hi Alice,\nYour password was typed on a fake sign-in page.")
    assert "1. Change your work password now" in note
    s = helpers.incident_summary("credential_phishing", Severity.CRITICAL, ["password_reuse"],
                                 messages=14, recipients=7, departments=3, employee="Alice")
    assert s.startswith("A credential phishing attack") and "14 messages, 7 recipients, 3 departments" in s


def test_llm_text_with_invented_facts_is_dropped(monkeypatch):
    answer_with(monkeypatch, {"what_happened": "Someone from evil.example logged in 5 times."})
    note = helpers.employee_notification("Alice", "credential_phishing", ["password_reuse"])
    assert "evil.example" not in note and note.startswith("Hi Alice,\nWe detected")
