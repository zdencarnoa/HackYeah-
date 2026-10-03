import pytest

from app.detection import detect, message_from_sim, parse_eml
from app.detection.content import MAX_QUOTE, check_content
from app.schemas import SignalCategory
from app.simulation.seed import load_emails
from tests.detection.helpers import make_eml

EMAILS = load_emails()
BY_ID = {sim.id: sim for sim in EMAILS}
CAMPAIGN = [sim for sim in EMAILS if sim.scenario.campaign_id == "camp-ms-verify"]
LEGIT = [sim for sim in EMAILS if sim.scenario.label == "legitimate"]


def content_signals(text="Hello", **eml):
    return check_content(parse_eml(make_eml(text=text, **eml))).signals


def by_category(signals):
    return {s.category: s for s in signals}


@pytest.mark.parametrize(("text", "category", "severity"), [
    ("Your account will be suspended within 24 hours.", SignalCategory.URGENCY, 2),
    ("This is your FINAL NOTICE before legal action.", SignalCategory.URGENCY, 2),
    ("Your mailbox expires in 12 hours.", SignalCategory.URGENCY, 2),
    ("Please verify your account to keep using email.", SignalCategory.CREDENTIAL_REQUEST, 2),
    ("Sign in with your work email to view the document.", SignalCategory.CREDENTIAL_REQUEST, 2),
    ("Re-enter your password at the link below.", SignalCategory.CREDENTIAL_REQUEST, 2),
    ("Please note our new bank details for all future invoices.", SignalCategory.PAYMENT_CHANGE, 3),
    ("Do not use the old account any more.", SignalCategory.PAYMENT_CHANGE, 3),
    ("Please transfer the amount to our new account.", SignalCategory.PAYMENT_CHANGE, 3),
    ("Our updated account is GB82 WEST 1234 5698 7654 32.", SignalCategory.PAYMENT_CHANGE, 3),
    ("Buy three Google Play cards and scratch off the code.", SignalCategory.GIFT_CARD, 3),
    ("Please read me the code you got by text message.", SignalCategory.MFA_CODE_REQUEST, 3),
    ("Send me the 6-digit code so I can finish the setup.", SignalCategory.MFA_CODE_REQUEST, 3),
    ("You will get several prompts. Please approve all of them.", SignalCategory.MFA_CODE_REQUEST, 3),
])
def test_each_category_fires(text, category, severity):
    signal = by_category(content_signals(text))[category]
    assert (signal.id, signal.severity, signal.source) == (f"content.{category}", severity, "rule")


@pytest.mark.parametrize("text", [
    "Please find attached invoice INV-20431. Please pay by Friday to the bank account already on file.",
    "This confirms that the password for your account was changed today. If you made this change, no action is needed.",
    "Logistics Weekly: Rotterdam congestion eases. Read online or unsubscribe.",
    "This is not urgent, but could you look at the draft? No action required before Monday.",
    "Can you send me the code review notes and the gift shop opening hours?",
    "Your new account for the travel portal is ready.",
])
def test_ordinary_business_mail_gets_no_content_signal(text):
    assert content_signals(text) == []


def test_one_signal_per_category_however_many_matches():
    text = ("URGENT: act now. Your account will be suspended immediately.\n"
            "This is your final notice, respond within 2 hours or lose access.")
    signals = content_signals(text)
    assert [s.category for s in signals] == [SignalCategory.URGENCY]
    assert "'urgent'" in signals[0].technical_detail and "'final notice'" in signals[0].technical_detail


def test_evidence_quotes_one_sentence_of_the_email():
    text = "Hello Alice.\nWe saw strange things. Your account will be\nsuspended today! Thanks."
    evidence = by_category(content_signals(text))[SignalCategory.URGENCY].evidence
    assert evidence == 'The email pushes you to act fast: "Your account will be suspended today!"'


def test_quote_is_cut_to_the_limit_around_the_match():
    filler = "This sentence keeps going with words that say nothing at all " * 4
    text = f"{filler}and then your account will be suspended for good {filler}."
    evidence = by_category(content_signals(text))[SignalCategory.URGENCY].evidence
    quote = evidence.split('"')[1]
    assert len(quote) <= MAX_QUOTE
    assert "will be suspended" in quote
    assert quote.startswith("…") and quote.endswith("…")


def test_text_after_a_colon_line_is_a_new_sentence():
    text = "Verify your account now:\nhttps://login.micr0soft-example.test/verify\n"
    evidence = by_category(content_signals(text))[SignalCategory.CREDENTIAL_REQUEST].evidence
    assert evidence.endswith('"Verify your account now"')


def test_subject_is_scanned():
    signal = by_category(content_signals("See below.", Subject="Updated bank details - invoice 7"))[
        SignalCategory.PAYMENT_CHANGE]
    assert signal.evidence.endswith('"Updated bank details - invoice 7"')
    assert "found in subject" in signal.technical_detail


def test_html_part_is_scanned_even_when_the_text_part_is_harmless():
    html = "<p>Your mailbox is full.</p><p>Please <b>confirm your password</b> to keep it.</p>"
    signal = by_category(content_signals("Your mailbox is full.", html=html))[
        SignalCategory.CREDENTIAL_REQUEST]
    assert signal.evidence.endswith('"Please confirm your password to keep it."')
    assert "found in HTML body" in signal.technical_detail


def test_html_only_email_is_scanned():
    html = "<p>Buy 5 gift cards today.</p>"
    assert by_category(content_signals(text=None, html=html))[SignalCategory.GIFT_CARD]


def test_empty_and_huge_bodies_do_not_break_the_check():
    assert check_content(parse_eml(b"From: a@example.test\r\n\r\n")).signals == []
    huge = ("word " * 200_000) + "verify your account"
    assert check_content(parse_eml(make_eml(text=huge))).signals == []  # beyond the scan limit


@pytest.mark.parametrize("sim", CAMPAIGN, ids=lambda sim: sim.id)
def test_microsoft_campaign_pushes_and_asks_for_credentials(sim):
    categories = {s.category for s in check_content(message_from_sim(sim)).signals}
    assert {SignalCategory.URGENCY, SignalCategory.CREDENTIAL_REQUEST} <= categories


@pytest.mark.parametrize("sim", LEGIT, ids=lambda sim: sim.id)
def test_legitimate_demo_mail_has_no_strong_content_signal(sim):
    signals = check_content(message_from_sim(sim)).signals
    assert all(s.severity < 2 for s in signals), [s.evidence for s in signals]


@pytest.mark.parametrize(("email_id", "category"), [
    ("phi-01", SignalCategory.PAYMENT_CHANGE),
    ("phi-02", SignalCategory.GIFT_CARD),
    ("phi-03", SignalCategory.MFA_CODE_REQUEST),
])
def test_scam_emails_fire_their_category(email_id, category):
    signals = by_category(check_content(message_from_sim(BY_ID[email_id])).signals)
    assert signals[category].severity == 3


def test_cmp_02_final_notice_quote():
    signals = by_category(check_content(message_from_sim(BY_ID["cmp-02"])).signals)
    assert signals[SignalCategory.CREDENTIAL_REQUEST].evidence.endswith(
        '"Verify immediately to avoid losing access"')


def test_detect_includes_content_signals():
    ids = {s.id for s in detect(message_from_sim(BY_ID["cmp-01"])).signals}
    assert {"content.urgency", "content.credential_request"} <= ids
