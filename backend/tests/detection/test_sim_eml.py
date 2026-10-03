from datetime import UTC, datetime

import pytest

from app.detection import message_from_sim, parse_eml, render_eml
from app.schemas import Link
from app.simulation.seed import load_emails

DELIVERED = datetime(2026, 10, 3, 9, 2, tzinfo=UTC)
EMAILS = load_emails()
BY_ID = {sim.id: sim for sim in EMAILS}
# Everything a rendered message may carry at the top level. Ground truth such as
# the scenario label must never reach detection.
MAIL_HEADERS = {"Received", "Authentication-Results", "From", "To", "Cc", "Reply-To", "Subject",
                "Date", "Message-ID", "MIME-Version", "Content-Type", "Content-Transfer-Encoding"}


@pytest.mark.parametrize("sim", EMAILS, ids=lambda sim: sim.id)
def test_every_demo_email_round_trips(sim):
    message = message_from_sim(sim, DELIVERED)

    assert message.id == sim.id
    assert message.sender == sim.sender_address.lower()
    assert message.sender_name == sim.sender_name
    assert message.reply_to == sim.reply_to
    assert message.recipients == [address.lower() for address in sim.to + sim.cc]
    assert message.subject == sim.subject
    assert message.body_text.rstrip("\n") == sim.body_text.rstrip("\n")
    assert (message.body_html or "").rstrip("\n") == (sim.body_html or "").rstrip("\n")
    assert message.received_at == DELIVERED
    assert set(sim.urls) <= {link.url for link in message.urls}
    assert [(a.filename, a.content_type, a.size_bytes, a.encrypted) for a in message.attachments] == [
        (a.filename, a.content_type, a.size_bytes, False) for a in sim.attachments]

    auth = dict(message.headers)["Authentication-Results"]
    for mechanism in ("spf", "dkim", "dmarc"):
        assert f"{mechanism}={getattr(sim.auth, mechanism)}" in auth


@pytest.mark.parametrize("sim", EMAILS, ids=lambda sim: sim.id)
def test_rendering_is_reproducible_and_carries_no_ground_truth(sim):
    raw = render_eml(sim, DELIVERED)
    assert raw == render_eml(sim, DELIVERED)
    assert {name for name, _ in parse_eml(raw).headers} <= MAIL_HEADERS


def test_html_variant_link_shows_one_address_and_leads_to_another():
    url = "https://login.micr0soft-example.test/verify?session=7f3a00c9"
    message = message_from_sim(BY_ID["cmp-01"], DELIVERED)
    assert message.urls == [
        Link(url=url, anchor_text="Verify your account now", found_in="html"),
        Link(url=url, anchor_text="https://account.microsoft.example/security/verify", found_in="html"),
    ]


def test_delivery_time_defaults_to_now():
    received_at = message_from_sim(BY_ID["leg-01"]).received_at
    assert abs((datetime.now(UTC) - received_at).total_seconds()) < 60
