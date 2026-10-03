import pytest

from app.detection import detect, message_from_sim, parse_eml
from app.detection.sender import check_sender
from app.schemas import SignalCategory
from app.simulation.seed import load_emails
from tests.detection.helpers import make_eml

EMAILS = load_emails()
BY_ID = {sim.id: sim for sim in EMAILS}
CAMPAIGN = [sim for sim in EMAILS if sim.scenario.campaign_id == "camp-ms-verify"]
LEGIT = [sim for sim in EMAILS if sim.scenario.label == "legitimate"]
ATTACK_URL = "https://login.micr0soft-example.test/verify"


def sender_signals(**eml):
    return check_sender(parse_eml(make_eml(**eml))).signals


def only(signals):
    assert len(signals) == 1, [s.evidence for s in signals]
    return signals[0]


# Rule 1: the display name claims a brand.

def test_brand_display_name_on_a_foreign_domain():
    s = only(sender_signals(From="Microsoft Security <security@micr0soft-example.test>"))
    assert (s.id, s.category, s.severity, s.source) == (
        "sender.brand_name", SignalCategory.BRAND_IMPERSONATION, 3, "rule")
    assert s.evidence == ("The sender calls itself 'Microsoft Security', but the email comes from "
                          "micr0soft-example.test, which is not a Microsoft address.")


@pytest.mark.parametrize("sender", [
    "Microsoft Security <security@outlook.com>",  # anyone can open an outlook.com mailbox
    "Google Accounts <accounts.team@gmail.com>",
    "Lakeside Logistics IT <lakeside.it@wp.pl>",
])
def test_brand_display_name_on_free_mail_is_flagged(sender):
    s = only(sender_signals(From=sender))
    assert (s.id, s.severity) == ("sender.brand_name", 3)
    assert "personal" in s.evidence


@pytest.mark.parametrize("sender", [
    "Microsoft <account-security-noreply@accountprotection.microsoft.com>",
    "Microsoft 365 <no-reply@microsoft.example>",
    "Microsoft Teams for Lakeside Logistics <noreply@email.teams.microsoft.com>",
    "IT Helpdesk <helpdesk@lakeside-logistics.example>",
    "Payroll <payroll@hr.lakeside-logistics.example>",
    "ParcelNow <notifications@track.parcelnow.example>",
    "Google <no-reply@accounts.google.com>",
    "DHL Express <noreply@dhl.com>",
    "InPost <powiadomienia@inpost.pl>",
    "PKO BP <kontakt@pkobp.pl>",
])
def test_real_brand_domains_and_subdomains_are_never_flagged(sender):
    assert sender_signals(From=sender) == []


@pytest.mark.parametrize("sender", [
    "Dhlomo Consulting <office@dhlomo.example>",     # "dhl" only as a whole word
    "Freight Market Outlook <news@market.example>",  # "outlook" alone is an everyday word
    "Mitch from Lakeside Hotel <mitch@lakeside-hotel.example>",
])
def test_brand_keywords_match_whole_words_only(sender):
    assert sender_signals(From=sender) == []


# Rule 2: a neutral display name, but the subject or signature names a brand.

def test_signature_names_a_brand_but_links_go_elsewhere():
    s = only(sender_signals(From="Account Team <noreply@secure-mail.test>",
                            text=f"Your mailbox is full.\n{ATTACK_URL}\n\nMicrosoft Security Team"))
    assert (s.id, s.category, s.severity) == ("sender.brand_content", SignalCategory.BRAND_IMPERSONATION, 2)
    assert s.evidence == ("The email is signed as Microsoft, but its links lead to "
                          "micr0soft-example.test, not to a Microsoft website.")


def test_subject_only_mention_is_weak():
    s = only(sender_signals(From="Account Team <noreply@secure-mail.test>",
                            Subject="Your Microsoft 365 password expires today",
                            text=f"Keep your password: {ATTACK_URL}\n\nAccount Team"))
    assert (s.id, s.severity) == ("sender.brand_content", 1)
    assert s.evidence.startswith("The subject mentions Microsoft")


@pytest.mark.parametrize("eml", [
    # A newsletter that writes about a brand in its body.
    {"From": "Logistics Weekly <newsletter@logisticsweekly.example>",
     "text": "Microsoft and DHL announce a partnership.\nhttps://logisticsweekly.example/212\n\nLogistics Weekly"},
    # The brand is named, but every link goes to the brand itself.
    {"From": "Account Team <noreply@secure-mail.test>",
     "text": "Review your sign-ins: https://account.microsoft.com/activity\n\nMicrosoft account team"},
    # Internal mail about a brand is not impersonation.
    {"From": "Oliver Martin <oliver.martin@lakeside-logistics.example>", "Subject": "Microsoft 365 rollout",
     "text": "Training: https://training.vendor.example/m365\n\nOliver\nMicrosoft 365 project"},
    # No links, so there is nothing to compare.
    {"From": "Account Team <noreply@secure-mail.test>", "text": "Call us.\n\nMicrosoft Security Team"},
])
def test_brand_content_rule_stays_quiet_on_ordinary_mail(eml):
    assert sender_signals(**eml) == []


# Rule 3: free-mail claiming a company role.

def test_free_mail_display_name_with_a_role():
    s = only(sender_signals(From="Finance Department <payments.dept@gmail.com>"))
    assert (s.id, s.category, s.severity) == (
        "sender.freemail_role", SignalCategory.FREEMAIL_IMPERSONATION, 2)
    assert s.evidence == ("The sender calls themselves 'Finance Department' but writes from a "
                          "personal gmail.com address, not a company one.")


def test_free_mail_signature_with_a_role():
    s = only(sender_signals(From="John Kowalski <john.k@wp.pl>",
                            text="Please pay the attached invoice today.\n\nJohn Kowalski\nChief Financial Officer\n"
                                 "Sent from my iPhone"))
    assert s.id == "sender.freemail_role"
    assert s.evidence == ("The email is signed 'Chief Financial Officer' but comes from a personal "
                          "wp.pl address, not a company one.")


@pytest.mark.parametrize("eml", [
    {"From": "John <john.k@wp.pl>", "text": "Thanks for the photos!\n\nJohn"},
    {"From": "John <john.k@wp.pl>", "text": "Can you send it today? I need it\nThanks"},  # "it", not "IT"
    {"From": "Anna Nowak, CEO <anna@nowak-transport.example>", "text": "Hi"},             # not free-mail
])
def test_free_mail_rule_needs_free_mail_and_a_role(eml):
    assert sender_signals(**eml) == []


# Rule 4: a colleague's name from outside the company.

def test_colleague_name_from_free_mail():
    signals = sender_signals(From="James Clark <james.clark.ceo@freemail.test>",
                             text="I need a favour. Buy gift cards.\n\nJames, CEO")
    s = only(signals)  # the CEO role claim is not reported twice
    assert (s.id, s.category, s.severity) == (
        "sender.colleague_name", SignalCategory.COLLEAGUE_IMPERSONATION, 3)
    assert s.evidence == ("The sender uses the name of your colleague James Clark (Chief Executive "
                          "Officer) but writes from a personal freemail.test address.")


def test_colleague_name_reversed_from_another_company():
    s = only(sender_signals(From='"Clark, James" <j.clark@partner-mail.example>'))
    assert (s.id, s.severity) == ("sender.colleague_name", 2)
    assert s.evidence.endswith("but writes from partner-mail.example, outside the company.")


@pytest.mark.parametrize("sender", [
    "James Clark <james.clark@lakeside-logistics.example>",
    "Bob Smithson <bob@smithson.example>",
    "James <james@partner-mail.example>",
])
def test_colleague_rule_needs_a_full_name_and_an_outside_address(sender):
    assert sender_signals(From=sender) == []


# Odd input.

@pytest.mark.parametrize("from_header", [None, "Microsoft Security"])
def test_missing_sender_address_is_reported_as_unchecked(from_header):
    result = check_sender(parse_eml(make_eml(From=from_header)))
    assert result.signals == []
    assert result.unchecked == ["We could not check who sent this email, because it has no sender address."]


def test_long_display_name_is_shortened_in_evidence():
    s = only(sender_signals(From=f"Microsoft {'Security ' * 40}<a@evil.test>"))
    assert len(s.evidence) < 200


def test_empty_display_name_is_fine():
    assert sender_signals(From="someone@evil.test") == []


# Demo dataset.

@pytest.mark.parametrize("sim", CAMPAIGN, ids=lambda sim: sim.id)
def test_every_microsoft_variant_is_brand_impersonation(sim):
    signals = check_sender(message_from_sim(sim)).signals
    assert any(s.category == SignalCategory.BRAND_IMPERSONATION and s.severity == 3 for s in signals)


@pytest.mark.parametrize("sim", LEGIT, ids=lambda sim: sim.id)
def test_legitimate_email_has_no_strong_sender_signal(sim):
    signals = check_sender(message_from_sim(sim)).signals
    assert all(s.severity < 2 for s in signals), [s.evidence for s in signals]


@pytest.mark.parametrize(("email_id", "category", "severity"), [
    ("phi-01", SignalCategory.BRAND_IMPERSONATION, 3),      # Paperline from paperline-supp1ies.test
    ("phi-02", SignalCategory.COLLEAGUE_IMPERSONATION, 3),  # "James Clark" on free-mail
    ("phi-03", SignalCategory.BRAND_IMPERSONATION, 3),      # "IT Security" from lakeside-it-support.test
    ("phi-04", SignalCategory.BRAND_IMPERSONATION, 3),      # ParcelNow from parcelnow-redelivery.test
    ("phi-05", SignalCategory.BRAND_IMPERSONATION, 3),      # "HR Portal" from lakesidelogistics-hr.test
    ("phi-06", SignalCategory.COLLEAGUE_IMPERSONATION, 2),  # "Bob Smith via FileShare"
])
def test_dataset_phishing_sender_signals(email_id, category, severity):
    signals = check_sender(message_from_sim(BY_ID[email_id])).signals
    assert (category, severity) in {(s.category, s.severity) for s in signals}, [s.evidence for s in signals]


def test_detect_reports_brand_impersonation_on_the_demo_email():
    first = message_from_sim(BY_ID["cmp-01"])
    result = detect(first)
    assert "sender.brand_name" in {s.id for s in result.signals}
    assert result == detect(first)  # deterministic
