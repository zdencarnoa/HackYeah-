import pytest

from app.llm import client, explain as explain_module, helpers
from app.llm.grounding import grounded
from app.llm.prompts import explanation_messages, fingerprint
from app.schemas import Signal, SignalCategory as C
from app.schemas import Severity
from app.scoring.fusion import fuse

EVIDENCE = "The sender's domain micr0soft-example.test imitates Microsoft."


def signals():
    return fuse([Signal(id="d.lookalike", category=C.LOOKALIKE_DOMAIN, severity=3, evidence=EVIDENCE,
                        technical_detail="-", source="rule")]).signals


@pytest.fixture(autouse=True)
def no_cache_no_live(monkeypatch):
    monkeypatch.setattr(client, "_cached", lambda: {})
    monkeypatch.setenv("LLM_LIVE", "0")


def answer_with(monkeypatch, answer):
    monkeypatch.setattr(explain_module, "ask", lambda messages, live=True, allow_local=True: (answer, "cache"))
    monkeypatch.setattr(helpers, "ask", lambda messages, live=True, allow_local=True: (answer, "cache"))


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


def incident(*evidence, type_="credential_phishing", severity=Severity.CRITICAL):
    from datetime import datetime, timezone
    from app.schemas import Evidence, Incident
    return Incident(id="inc-1", type=type_, severity=severity, affected_employees=["e01"], timeline=[],
                    created_at=datetime.now(timezone.utc),
                    evidence=[Evidence(employee_id="e01", **e) for e in evidence])


ALICE_PHISHED = [{"kind": "email_scored"}, {"kind": "link_clicked", "domain": "micr0soft-verify.example"},
                 {"kind": "password_reuse", "domain": "micr0soft-verify.example"}]


def test_without_an_llm_answer_helpers_return_empty_so_c_uses_its_template():
    inc = incident(*ALICE_PHISHED)
    assert helpers.employee_notification(inc, "e01") == ""
    assert helpers.incident_summary(inc) == ""
    assert helpers.checklist_reason("credential_phishing", "revoke_sessions", "C's reason") == ""


def test_llm_writes_the_story_but_steps_and_counts_stay_deterministic(monkeypatch):
    answer_with(monkeypatch, {"what_happened": "Your password was typed on a fake sign-in page.",
                              "summary": "A credential phishing attack reached the stage of a stolen password."})
    inc = incident(*ALICE_PHISHED)
    note = helpers.employee_notification(inc, "e01")
    assert note.startswith("Hi Alice,\nYour password was typed on a fake sign-in page.")
    assert "1. Change your work password now" in note
    s = helpers.incident_summary(inc)
    assert s.startswith("A credential phishing attack") and "3 detected automatically" in s


def test_llm_text_with_invented_facts_is_dropped(monkeypatch):
    answer_with(monkeypatch, {"what_happened": "Someone from evil.example logged in 5 times.",
                              "rationale": "Attackers from evil.example are blocked."})
    assert helpers.employee_notification(incident(*ALICE_PHISHED), "e01") == ""
    assert helpers.checklist_reason("credential_phishing", "block_sender_domain", "Blocks the sender.") == ""


def test_c_hooks_use_b_helpers_when_an_llm_answer_exists(monkeypatch):
    """Through Person C's real ai_hooks: B's text is used and labelled llm."""
    from app.incidents import ai_hooks
    answer_with(monkeypatch, {"what_happened": "A fake page received your password.",
                              "summary": "Credential phishing reached a stolen password.",
                              "rationale": "Ending sessions locks out anyone already signed in."})
    inc = incident(*ALICE_PHISHED)
    assert ai_hooks.incident_summary(inc)[1] == "llm"
    assert ai_hooks.employee_notification(inc, "e01")[1] == "llm"
    assert ai_hooks.checklist_reason("credential_phishing", "revoke_sessions", "C's reason") == "C's reason"


def test_c_hooks_fall_back_to_c_templates_without_an_llm():
    from app.incidents import ai_hooks
    inc = incident(*ALICE_PHISHED)
    assert ai_hooks.incident_summary(inc)[1] == "template"
    assert ai_hooks.employee_notification(inc, "e01")[1] == "template"
    assert ai_hooks.checklist_reason("credential_phishing", "revoke_sessions", "C's reason") == "C's reason"
