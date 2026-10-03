import pytest

from app.detection import detect, message_from_sim, parse_eml
from app.detection.urls import check_urls
from app.schemas import Link, SignalCategory
from app.simulation.seed import load_emails
from tests.detection.helpers import make_eml

BY_ID = {sim.id: sim for sim in load_emails()}
LEGIT = [sim for sim in load_emails() if sim.scenario.label == "legitimate"]
ATTACK_URL = "https://login.micr0soft-example.test/verify?session=7f3a00c9"


def signals_for(text="Hello", html=None):
    return {s.id: s for s in check_urls(parse_eml(make_eml(text=text, html=html))).signals}


def signals_for_links(*urls):
    """Links set directly, so URLs that ingestion would never produce can be tested too."""
    message = parse_eml(make_eml()).model_copy(update={"urls": [Link(url=u, found_in="text") for u in urls]})
    return {s.id: s for s in check_urls(message).signals}


def anchor(href, text):
    return f'<p><a href="{href}">{text}</a></p>'


def test_link_text_showing_another_site_is_a_mismatch():
    signal = signals_for(html=anchor(ATTACK_URL, "https://account.microsoft.example/verify"))["url.text_mismatch"]
    assert signal.severity == 3
    assert signal.category == SignalCategory.SUSPICIOUS_URL
    assert signal.source == "url"
    assert signal.evidence == ("The link shows account.microsoft.example but actually leads to "
                               "login.micr0soft-example.test.")
    assert "registrable micr0soft-example.test" in signal.technical_detail


@pytest.mark.parametrize("text", ["account.microsoft.com", "Go to www.microsoft.com now",
                                  "Sign in at ACCOUNT.MICROSOFT.COM", "lakeside-logistics.example"])
def test_bare_domain_in_link_text_counts(text):
    assert "url.text_mismatch" in signals_for(html=anchor("https://evil.example/login", text))


@pytest.mark.parametrize(("href", "text"), [
    (ATTACK_URL, "Click here"),
    (ATTACK_URL, "Verify your account now"),
    (ATTACK_URL, ATTACK_URL),
    ("https://www.microsoft.com/account", "microsoft.com"),
    ("https://microsoft.com/account", "www.microsoft.com"),
    ("https://login.lakeside-logistics.example/a", "lakeside-logistics.example"),
    ("https://files.lakeside-logistics.example/s/1", "Salary adjustments 2027.pdf"),
    ("https://files.lakeside-logistics.example/s/2", "INV-20431.pdf"),
    ("https://files.lakeside-logistics.example/s/3", "invoice.pdf.exe and report.docx"),
    ("https://files.lakeside-logistics.example/s/4", "Release notes, e.g. version 2.0.1"),
    ("https://files.lakeside-logistics.example/s/5", "Write to help@microsoft.com"),
])
def test_no_mismatch(href, text):
    assert "url.text_mismatch" not in signals_for(html=anchor(href, text))


def test_at_sign_hides_the_real_host():
    signal = signals_for("Sign in: https://microsoft.com@evil.example/login")["url.at_sign"]
    assert signal.severity == 3
    assert signal.evidence == "The link looks like it goes to microsoft.com but really goes to evil.example."
    assert "url.at_sign" not in signals_for("See https://evil.example/?email=alice@lakeside-logistics.example")


@pytest.mark.parametrize(("url", "shown"), [
    ("http://192.0.2.10/login", "192.0.2.10"),
    ("http://[2001:db8::1]/x", "2001:db8::1"),
    ("http://3221225994/x", "192.0.2.10"),  # the same address written as one number
])
def test_ip_host(url, shown):
    signal = signals_for_links(url)["url.ip_host"]
    assert signal.severity == 2
    assert f"({shown})" in signal.evidence


def test_brand_domain_in_the_subdomain():
    signal = signals_for("https://microsoft.com.account-check.example/login")["url.brand_subdomain"]
    assert signal.severity == 2
    assert signal.evidence == "The address starts with 'microsoft.com', but the real website is account-check.example."


@pytest.mark.parametrize("url", ["https://account.microsoft.com/x", "https://login.lakeside-logistics.example/",
                                 "https://office.com.sharepoint.com/x"])
def test_brand_own_subdomains_are_fine(url):
    assert "url.brand_subdomain" not in signals_for_links(url)


def test_deep_subdomain():
    assert signals_for_links("https://a.b.c.evil.example/")["url.deep_subdomain"].severity == 1
    assert "url.deep_subdomain" not in signals_for_links("https://www.shop.example.co.uk/")
    assert "url.deep_subdomain" not in signals_for_links("https://b.c.evil.example/")


def test_punycode_and_foreign_letters():
    lookalike = "mіcrosoft.com"  # Cyrillic "і"
    encoded = "xn--" + "mіcrosoft".encode("punycode").decode() + ".com"
    for url in (f"https://{encoded}/login", f"https://{lookalike}/login"):
        signal = signals_for_links(url)["url.punycode"]
        assert signal.severity == 2
        assert lookalike in signal.evidence
        assert encoded in signal.technical_detail
    html = anchor(f"https://{lookalike}/login", "Sign in")
    assert "url.punycode" in signals_for(text=None, html=html)


def test_shortener_is_weak_and_never_expanded():
    signal = signals_for("Details: https://bit.ly/3xYz9 and https://www.tinyurl.com/abc")["url.shortener"]
    assert signal.severity == 1
    assert "bit.ly" in signal.evidence
    assert "tinyurl.com" in signal.technical_detail


@pytest.mark.parametrize(("path", "fires"), [
    ("/account/login", True), ("/signin.php", True), ("/verify", True), ("/user/password-reset", True),
    ("/insecure-news", False), ("/issues/212", False), ("/benefits", False),
])
def test_login_path(path, fires):
    assert ("url.login_path" in signals_for_links(f"https://x.example{path}")) == fires


def test_one_signal_per_rule_with_up_to_three_links():
    signals = signals_for_links(*[f"https://x{i}.example/login" for i in range(5)])
    assert list(signals) == ["url.login_path"]
    assert signals["url.login_path"].technical_detail.count("login-path keyword") == 3


@pytest.mark.parametrize("url", ["http://[::1", "https://:80/", "http://", "https://x.example:99999999/a",
                                 "https://xn--zz.example/", "not a url at all"])
def test_garbage_urls_do_not_raise(url):
    signals_for_links(url)


def test_deterministic():
    message = message_from_sim(BY_ID["cmp-01"])
    assert check_urls(message) == check_urls(message)


@pytest.mark.parametrize("sim_id", ["cmp-01", "cmp-02"])
def test_html_campaign_variants_show_microsoft_but_lead_elsewhere(sim_id):
    signal = {s.id: s for s in check_urls(message_from_sim(BY_ID[sim_id])).signals}["url.text_mismatch"]
    assert signal.severity == 3
    assert "login.micr0soft-example.test" in signal.evidence


def test_whole_campaign_links_to_a_verify_page():
    campaign = [sim for sim in load_emails() if sim.scenario.campaign_id == "camp-ms-verify"]
    for sim in campaign:
        assert "url.login_path" in {s.id for s in check_urls(message_from_sim(sim)).signals}, sim.id


@pytest.mark.parametrize("sim", LEGIT, ids=lambda sim: sim.id)
def test_legitimate_demo_mail_has_no_strong_url_signal(sim):
    signals = check_urls(message_from_sim(sim)).signals
    assert all(s.severity < 2 for s in signals), [s.evidence for s in signals]


def test_detect_includes_url_signals():
    assert "url.text_mismatch" in {s.id for s in detect(message_from_sim(BY_ID["cmp-01"])).signals}
