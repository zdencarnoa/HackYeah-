from urllib.parse import urlsplit

import pytest
from bs4 import BeautifulSoup

from app.detection import clear_links, detect, message_from_sim, parse_eml, rewrite, rewrite_links
from app.schemas import SimEventType
from app.simulation.seed import load_emails
from tests.detection.helpers import make_eml

BY_ID = {sim.id: sim for sim in load_emails()}
ATTACK_URL = "https://login.micr0soft-example.test/verify?session=7f3a00c9"


@pytest.fixture(autouse=True)
def fresh_links(monkeypatch):
    """Each test gets its own token store and click list."""
    monkeypatch.setattr(rewrite, "_store", rewrite.InMemoryLinkStore())
    monkeypatch.setattr(rewrite, "_on_click", rewrite.log_click)
    monkeypatch.setattr(rewrite, "recorded_clicks", [])


def token_of(url: str) -> str:
    assert url.startswith(rewrite.BASE_URL + "/r/"), url
    return urlsplit(url).path.rsplit("/", 1)[1]


def hrefs(html: str) -> list[str]:
    return [a["href"] for a in BeautifulSoup(html, "html.parser").find_all("a", href=True)]


def test_every_link_in_the_inbox_copy_is_tracked_and_anchor_text_kept():
    original = message_from_sim(BY_ID["cmp-01"])
    copy = rewrite_links(original, "e01")

    assert all(href.startswith(rewrite.BASE_URL + "/r/") for href in hrefs(copy.body_html))
    assert [link.anchor_text for link in copy.urls] == [link.anchor_text for link in original.urls]
    assert "https://account.microsoft.example/security/verify" in copy.body_html  # visible text unchanged
    assert ATTACK_URL not in copy.body_text and "/r/" in copy.body_text
    assert original.urls[0].url == ATTACK_URL  # the original is never modified
    assert copy.id == original.id


def test_one_token_per_employee_and_url_reused_on_every_rewrite():
    original = message_from_sim(BY_ID["cmp-01"])
    alice, again = rewrite_links(original, "e01"), rewrite_links(original, "e01")
    carol = rewrite_links(original, "e03")
    assert alice.urls[0].url == again.urls[0].url == alice.urls[1].url  # same URL, same token
    assert alice.urls[0].url != carol.urls[0].url
    assert rewrite._store.get(token_of(carol.urls[0].url)).employee_id == "e03"


def test_plain_text_links_keep_their_punctuation_and_mail_links_stay():
    text = "Go to www.helpdesk.example/new, or https://a.example/x. Mail mailto:it@lakeside-logistics.example"
    copy = rewrite_links(parse_eml(make_eml(text)), "e01")
    tokens = [rewrite._store.get(token_of(url)) for url in
              [w.rstrip(".,") for w in copy.body_text.split() if "/r/" in w]]
    assert [t.original_url for t in tokens] == ["http://www.helpdesk.example/new", "https://a.example/x"]
    assert ", or " in copy.body_text and copy.body_text.rstrip().endswith("mailto:it@lakeside-logistics.example")
    assert ". Mail" in copy.body_text


def test_detection_must_run_on_the_original():
    """Why D analyzes before rewriting: on the copy, the lookalike link is gone and
    every link text that shows an address looks like a mismatch with localhost."""
    original = message_from_sim(BY_ID["cmp-01"])
    on_original = {s.id: s for s in detect(original).signals}
    on_copy = {s.id: s for s in detect(rewrite_links(original, "e01")).signals}
    assert "lookalike.link" in on_original and "lookalike.link" not in on_copy
    assert "localhost" in on_copy["url.text_mismatch"].evidence


def test_following_a_token_records_a_link_clicked_event():
    copy = rewrite_links(message_from_sim(BY_ID["cmp-01"]), "e01")
    record = rewrite.follow(token_of(copy.urls[0].url))

    assert record.original_url == ATTACK_URL
    (event,) = rewrite.recorded_clicks
    assert event.type == SimEventType.LINK_CLICKED
    assert (event.employee_id, event.message_id) == ("e01", "cmp-01")
    assert event.data == {"domain": "login.micr0soft-example.test", "url": ATTACK_URL, "source": "automatic"}
    assert event.simulated is True


def test_unknown_token_records_nothing():
    assert rewrite.follow("no-such-token") is None
    assert rewrite.recorded_clicks == []


def test_a_failing_click_handler_does_not_break_the_click():
    def broken(event):
        raise RuntimeError("intake down")

    rewrite.configure(on_click=broken)
    copy = rewrite_links(message_from_sim(BY_ID["cmp-01"]), "e01")
    assert rewrite.follow(token_of(copy.urls[0].url)).original_url == ATTACK_URL


def test_configure_plugs_in_another_store_and_handler():
    events, store = [], rewrite.InMemoryLinkStore()
    rewrite.configure(store=store, on_click=events.append)
    copy = rewrite_links(message_from_sim(BY_ID["cmp-01"]), "e01")
    rewrite.follow(token_of(copy.urls[0].url))
    assert store.get(token_of(copy.urls[0].url)) is not None
    assert len(events) == 1 and rewrite.recorded_clicks == []


@pytest.mark.parametrize(("url", "target"), [
    (ATTACK_URL, "/login.micr0soft-example.test/verify?session=7f3a00c9"),
    ("http://parcelnow-redelivery.test", "/parcelnow-redelivery.test/"),
    ("https://helpdesk.lakeside-logistics.example/new", "/helpdesk.lakeside-logistics.example/new"),
    ("https://www.microsoft.com/login", None),
    ("https://evil.example.com/login", None),  # ".example" must be the real ending
])
def test_only_demo_domains_get_a_target(url, target):
    record = rewrite._store.issue(url, "m1", "e01")
    expected = rewrite.DEMO_SITE_URL + target if target else None
    assert rewrite.demo_target(record) == expected


def test_clear_links_forgets_tokens_and_clicks():
    copy = rewrite_links(message_from_sim(BY_ID["cmp-01"]), "e01")
    token = token_of(copy.urls[0].url)
    rewrite.follow(token)
    clear_links()
    assert rewrite._store.get(token) is None and rewrite.recorded_clicks == []
