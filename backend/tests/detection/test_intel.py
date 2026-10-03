import ipaddress
import json
from urllib.parse import urlsplit

import pytest

from app.detection import detect, intel, message_from_sim, parse_eml
from app.detection.domains import domain_of
from app.detection.intel import NO_BLOCKLIST, check_intel
from app.schemas import SignalCategory
from app.simulation.seed import load_emails
from tests.detection.helpers import make_eml

EMAILS = load_emails()
BY_ID = {sim.id: sim for sim in EMAILS}
LEGIT = [sim for sim in EMAILS if sim.scenario.label == "legitimate"]
CAMPAIGN = [sim for sim in EMAILS if sim.scenario.campaign_id == "camp-ms-verify"]
REAL_LIST = json.loads(intel.BLOCKLIST_PATH.read_text(encoding="utf-8"))
TEST_LIST = {"updated": "2026-01-01", "note": "test list",
             "domains": ["bad.test"], "urls": ["https://pages.example/Phish/"],
             "senders": ["fraud@freemail.test"], "ips": ["192.0.2.66", "2001:db8::66", "not an ip"]}
DOCUMENTATION_NETS = [ipaddress.ip_network(n) for n in
                      ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32")]


@pytest.fixture
def test_list(tmp_path, monkeypatch):
    """Unit tests run against a small list of their own, not the demo snapshot."""
    path = tmp_path / "blocklist.json"
    path.write_text(json.dumps(TEST_LIST), encoding="utf-8")
    monkeypatch.setattr(intel, "BLOCKLIST_PATH", path)


def scan(raw: bytes) -> dict:
    return {signal.id: signal for signal in check_intel(parse_eml(raw)).signals}


def received(*hops: str) -> bytes:
    """Received headers on top of a clean email, topmost first."""
    return "".join(f"Received: from {hop} by mx.lakeside-logistics.example; "
                   "Sat, 03 Oct 2026 09:00:00 +0000\n" for hop in hops).encode() + make_eml()


@pytest.mark.parametrize("sender", ["billing@bad.test", "billing@mail.bad.test"])
def test_sender_domain_or_its_subdomain(test_list, sender):
    signal = scan(make_eml(From=f"Billing <{sender}>"))["intel.sender"]
    assert (signal.category, signal.severity, signal.source) == (SignalCategory.KNOWN_BAD, 3, "intel")
    assert signal.evidence == "The email comes from bad.test, which is on our list of known phishing domains."
    assert signal.technical_detail == (f"From {sender} matches domains entry 'bad.test'; "
                                       "blocklist updated 2026-01-01")


def test_sender_address_but_not_its_free_mail_provider(test_list):
    signal = scan(make_eml(From="fraud@freemail.test"))["intel.sender"]
    assert signal.evidence == "The sender fraud@freemail.test is on our list of known phishing senders."
    assert scan(make_eml(From="friend@freemail.test")) == {}


@pytest.mark.parametrize(("reply_to", "evidence"), [
    ("fraud@freemail.test", "Replies would go to fraud@freemail.test, which is on our list of known phishing senders."),
    ("pay@bad.test", "Replies would go to bad.test, which is on our list of known phishing domains."),
])
def test_reply_to(test_list, reply_to, evidence):
    assert scan(make_eml(Reply_To=reply_to))["intel.sender"].evidence == evidence


def test_link_host_on_a_listed_domain(test_list):
    signal = scan(make_eml("Pay at https://portal.bad.test/pay today."))["intel.link"]
    assert signal.evidence == "The link leads to bad.test, which is on our list of known phishing sites."
    assert signal.technical_detail.startswith("link host portal.bad.test matches domains entry 'bad.test'")


@pytest.mark.parametrize(("url", "listed"), [
    ("https://pages.example/Phish", True),
    ("HTTPS://PAGES.EXAMPLE/Phish/", True),
    ("https://pages.example/phish", False),  # paths are case-sensitive
    ("https://pages.example/Phish/other", False),
])
def test_full_url_matches_trivial_variants_only(test_list, url, listed):
    signals = scan(make_eml(f"See {url} now"))
    assert ("intel.link" in signals) is listed
    if listed:
        assert signals["intel.link"].evidence == (
            "The link to pages.example leads to a page on our list of known phishing sites.")


@pytest.mark.parametrize(("url", "ip"), [("http://192.0.2.66/login", "192.0.2.66"),
                                         ("http://[2001:db8::66]/login", "2001:db8::66")])
def test_link_to_a_listed_ip(test_list, url, ip):
    signal = scan(make_eml("Log in below.", html=f'<a href="{url}">Log in</a>'))["intel.ip"]
    assert signal.evidence == f"The link leads to a server ({ip}) that is on our list of known phishing sources."


@pytest.mark.parametrize("hop", ["mail.bad-host.test ([192.0.2.66])", "relay ([IPv6:2001:db8::66])"])
def test_sending_server_from_the_topmost_received_header(test_list, hop):
    signal = scan(received(hop))["intel.ip"]
    assert signal.evidence.startswith("This email was sent from a server (")
    assert "topmost Received IP" in signal.technical_detail


def test_forged_lower_received_header_is_ignored(test_list):
    assert scan(received("mail.example ([198.51.100.10])", "forged ([192.0.2.66])")) == {}


def test_several_hits_give_one_signal_per_rule(test_list):
    raw = make_eml("Pay at https://a.bad.test/x or https://b.bad.test/y", From="x@bad.test",
                   Reply_To="fraud@freemail.test")
    signals = scan(raw)
    assert sorted(signals) == ["intel.link", "intel.sender"]
    assert signals["intel.sender"].evidence.startswith("The email comes from bad.test")
    assert "a.bad.test" in signals["intel.link"].technical_detail
    assert "b.bad.test" in signals["intel.link"].technical_detail
    assert "Reply-To fraud@freemail.test" in signals["intel.sender"].technical_detail


@pytest.mark.parametrize("raw", [
    make_eml(),
    make_eml("Visit https://notbad.test/ or https://bad.test.evil.example/x", From="x@notbad.test"),
    make_eml("Visit http://192.0.2.67/ or http://[not-an-ip/", From="x@bad.testing.example"),
], ids=["clean", "similar-domains", "other-ip-and-broken-url"])
def test_unlisted_mail_gets_nothing(test_list, raw):
    result = check_intel(parse_eml(raw))
    assert result.signals == [] and result.unchecked == []


@pytest.mark.parametrize("content", [None, "{not json", "[]"], ids=["missing", "broken", "wrong-shape"])
def test_unreadable_blocklist_is_unchecked_not_an_error(tmp_path, monkeypatch, content):
    path = tmp_path / "blocklist.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(intel, "BLOCKLIST_PATH", path)
    result = check_intel(parse_eml(make_eml(From="x@bad.test")))
    assert result.signals == []
    assert result.unchecked == [NO_BLOCKLIST]


def test_demo_snapshot_uses_reserved_names_only():
    for domain in REAL_LIST["domains"]:
        assert domain.endswith((".example", ".test")), domain
    for sender in REAL_LIST["senders"]:
        assert domain_of(sender).endswith((".example", ".test")), sender
    for url in REAL_LIST["urls"]:
        assert (urlsplit(url).hostname or "").endswith((".example", ".test")), url
    for ip in REAL_LIST["ips"]:
        assert any(ipaddress.ip_address(ip) in net for net in DOCUMENTATION_NETS), ip


def test_microsoft_campaign_domain_is_not_on_the_list():
    """The demo catches it with no prior knowledge."""
    domains = frozenset(REAL_LIST["domains"])
    assert intel._listed_domain("login.micr0soft-example.test", domains) is None
    assert not any("micr0soft" in entry for key in ("domains", "urls", "senders") for entry in REAL_LIST[key])
    assert not {sim.sending_ip for sim in CAMPAIGN} & set(REAL_LIST["ips"])


@pytest.mark.parametrize("sim", LEGIT, ids=lambda sim: sim.id)
def test_no_legitimate_infrastructure_is_on_the_list(sim):
    domains = frozenset(REAL_LIST["domains"])
    addresses = [sim.sender_address] + ([sim.reply_to] if sim.reply_to else [])
    hosts = [domain_of(a) for a in addresses] + [urlsplit(u).hostname for u in sim.urls]
    assert not [h for h in hosts if intel._listed_domain(h, domains)]
    assert not {a.lower() for a in addresses} & set(REAL_LIST["senders"])
    assert not set(sim.urls) & set(REAL_LIST["urls"])
    assert sim.sending_ip not in REAL_LIST["ips"]


@pytest.mark.parametrize(("sim_id", "rules"), [
    ("phi-01", {"intel.sender", "intel.ip"}),
    ("phi-04", {"intel.sender", "intel.link", "intel.ip"}),
    ("phi-07", {"intel.sender", "intel.link", "intel.ip"}),
])
def test_background_phishing_is_known_bad(sim_id, rules):
    signals = check_intel(message_from_sim(BY_ID[sim_id])).signals
    assert {s.id for s in signals} == rules
    assert all(s.category == SignalCategory.KNOWN_BAD and s.severity == 3 for s in signals)


@pytest.mark.parametrize("sim", CAMPAIGN + LEGIT, ids=lambda sim: sim.id)
def test_campaign_and_legitimate_mail_are_not_known_bad(sim):
    result = check_intel(message_from_sim(sim))
    assert result.signals == [] and result.unchecked == []


def test_detect_includes_intel_signals():
    result = detect(message_from_sim(BY_ID["phi-07"]))
    link = next(s for s in result.signals if s.id == "intel.link")
    assert link.evidence == "The link leads to docusafe-esign.test, which is on our list of known phishing sites."
