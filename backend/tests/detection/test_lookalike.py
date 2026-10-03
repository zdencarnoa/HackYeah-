import pytest

from app.detection import detect, message_from_sim, parse_eml
from app.detection.lookalike import check_lookalike, edit_distance, find_lookalike, normalize
from app.simulation.seed import load_emails
from tests.detection.helpers import make_eml

EMAILS = load_emails()
CAMPAIGN = [sim for sim in EMAILS if sim.scenario.campaign_id == "camp-ms-verify"]
LEGIT = [sim for sim in EMAILS if sim.scenario.label == "legitimate"]
BY_ID = {sim.id: sim for sim in EMAILS}
CYRILLIC_MICROSOFT = "micrоsoft".encode("idna").decode("ascii") + ".com"  # Cyrillic "о"


def test_normalize_records_which_substitution_was_made():
    assert normalize("micr0soft") == ("microsoft", (("0", "o"),))
    assert normalize("rnicrosoft") == ("microsoft", (("rn", "m"),))
    assert normalize("micrоsoft") == ("microsoft", (("о", "o"),))
    assert normalize("Microsoft") == ("microsoft", ())


@pytest.mark.parametrize(("a", "b", "distance"), [
    ("microsoft", "microsoft", 0), ("microsfot", "microsoft", 1), ("microsofft", "microsoft", 1),
    ("micosoft", "microsoft", 1), ("mlcrosoft", "microsoft", 1), ("macrosaft", "microsoft", 2),
])
def test_edit_distance_counts_a_swap_as_one_edit(a, b, distance):
    assert edit_distance(a, b) == distance


@pytest.mark.parametrize(("host", "brand", "trick"), [
    ("micr0soft-example.test", "microsoft", "the letter 'o' was replaced by the digit '0'"),
    ("rnicrosoft.test", "microsoft", "the letters 'rn' stand in for the letter 'm'"),
    ("m1crosoft.test", "microsoft", "the letter 'i' was replaced by the digit '1'"),
    ("microsfot.test", "microsoft", "the letters 'of' were swapped"),
    ("microsofft.test", "microsoft", "an extra 'f' was added to 'microsoft'"),
    (CYRILLIC_MICROSOFT, "microsoft",
     "the letter 'o' was replaced by a look-alike letter from another alphabet"),
    ("micr0softsupport.test", "microsoft", "the letter 'o' was replaced by the digit '0'"),
    ("paperline-supp1ies.test", "paperline", "the letter 'l' was replaced by the digit '1'"),
    ("0ffice365.test", "microsoft", "the letter 'o' was replaced by the digit '0'"),
    ("goog1e.com", "google", "the letter 'l' was replaced by the digit '1'"),
    # Short names match only exactly after undoing look-alikes, never by typo.
    ("dh1.com", "dhl", "the letter 'l' was replaced by the digit '1'"),
    # Combosquatting: the real name inside a longer domain is a reused name, not a trick.
    ("lakesidelogistics-hr.test", "company", ""),
    ("lakeside-it-support.test", "company", ""),
    ("parcelnow-redelivery.test", "parcelnow", ""),
    ("microsoft-0nline.test", "microsoft", ""),
])
def test_imitations_are_caught_and_the_trick_is_named(host, brand, trick):
    match = find_lookalike(host)
    assert match is not None and (match.target.key, match.trick) == (brand, trick)


@pytest.mark.parametrize("host", [
    # Real brand domains and their subdomains
    "microsoft.com", "account.microsoft.com", "accountprotection.microsoft.example", "dhl.com",
    "login.lakeside-logistics.example", "paperline-supplies.example", "track.parcelnow.example",
    # Free-mail providers, unrelated businesses and generic words
    "gmail.com", "outlook.com", "freemail.test", "logisticsweekly.example", "nordicfreight.example",
    "office-supplies.example", "fileshare-docs.test", "docusafe-esign.test",
    # No typo matching on short names
    "dhx.com", "dhll.com",
    # Not domains at all
    "192.0.2.10", "[2001:db8::1]", "localhost", "", "...",
])
def test_real_domains_and_unrelated_names_are_not_lookalikes(host):
    assert find_lookalike(host) is None


def test_sender_and_link_signals():
    raw = make_eml(text="Sign in: https://login.rnicrosoft.test/verify and https://parcelnow-redelivery.test/pay",
                   From="Account Team <team@micr0soft-example.test>")
    signals = {s.id: s for s in check_lookalike(parse_eml(raw)).signals}
    sender, link = signals["lookalike.sender"], signals["lookalike.link"]
    assert (sender.category, sender.severity, sender.source) == ("lookalike_domain", 3, "rule")
    assert sender.evidence == ("The sender's domain micr0soft-example.test imitates Microsoft: "
                               "the letter 'o' was replaced by the digit '0'.")
    assert "homoglyphs 0→o" in sender.technical_detail
    assert (link.category, link.severity, link.source) == ("suspicious_url", 3, "url")
    assert link.evidence == ("The link leads to login.rnicrosoft.test, an imitation of Microsoft: "
                             "the letters 'rn' stand in for the letter 'm'.")
    assert "parcelnow-redelivery.test" in link.technical_detail  # every lookalike link is listed


def test_combosquatting_evidence_for_our_company():
    raw = make_eml(text="Confirm: https://lakesidelogistics-hr.test/confirm", From="HR <hr@lakesidelogistics-hr.test>")
    evidence = [s.evidence for s in check_lookalike(parse_eml(raw)).signals]
    assert evidence == [
        "The sender's domain lakesidelogistics-hr.test uses our company's name, but it is not our company's domain.",
        "The link leads to lakesidelogistics-hr.test, which uses our company's name but is not our company's website.",
    ]


def test_no_signal_for_odd_input():
    raw = make_eml(text=None, html='<a href="http://[::1">x</a> <a href="https://192.0.2.10/login">ip</a>',
                   From="no-address")
    assert check_lookalike(parse_eml(raw)).signals == []


@pytest.mark.parametrize("sim", CAMPAIGN, ids=lambda sim: sim.id)
def test_every_microsoft_variant_has_a_lookalike_sender_and_link(sim):
    signals = {s.id: s for s in check_lookalike(message_from_sim(sim)).signals}
    assert signals["lookalike.sender"].severity == 3
    assert signals["lookalike.sender"].category == "lookalike_domain"
    assert signals["lookalike.link"].severity == 3
    assert signals["lookalike.link"].category == "suspicious_url"
    for signal in signals.values():
        assert len(signal.evidence.split()) <= 25, signal.evidence


@pytest.mark.parametrize("sim", LEGIT, ids=lambda sim: sim.id)
def test_legitimate_demo_mail_has_no_lookalike_signal(sim):
    signals = check_lookalike(message_from_sim(sim)).signals
    assert signals == [], [s.evidence for s in signals]


@pytest.mark.parametrize(("email_id", "expected"), [
    ("phi-01", {"lookalike.sender"}),  # paperline-supp1ies.test, no links
    ("phi-02", set()),  # free-mail
    ("phi-03", {"lookalike.sender", "lookalike.link"}),  # lakeside-it-support.test
    ("phi-04", {"lookalike.sender", "lookalike.link"}),  # parcelnow-redelivery.test
    ("phi-05", {"lookalike.sender", "lookalike.link"}),  # lakesidelogistics-hr.test
    ("phi-06", set()),  # fileshare-docs.test imitates no known name
    ("phi-07", set()),  # docusafe-esign.test imitates no known name
])
def test_other_phishing_emails(email_id, expected):
    assert {s.id for s in check_lookalike(message_from_sim(BY_ID[email_id])).signals} == expected


def test_detect_includes_lookalike_signals():
    ids = {s.id for s in detect(message_from_sim(BY_ID["cmp-01"])).signals}
    assert {"lookalike.sender", "lookalike.link"} <= ids
