"""A1: detection on what the attack engine really delivers (a DeliveredEmail via
`engine.on_deliver`), not only on dataset fixtures."""

from app.detection import detect, message_from_sim
from app.schemas import SignalCategory
from app.simulation.engine import AttackEngine
from app.simulation.events import EventBus
from app.simulation.seed import load_emails

AMBIGUOUS = "amb-01"


def deliver_everything():
    results = {}

    def on_deliver(delivered):
        message = message_from_sim(delivered, delivered.delivered_at)
        results[delivered.id] = (delivered, message, detect(message))

    engine = AttackEngine(EventBus(), on_deliver=on_deliver)
    engine.jump_to_demo_second(10**9)
    return results


RESULTS = deliver_everything()
SCENARIO = {sim.id: sim.scenario for sim in load_emails()}


# Signal severity is 0-3 (weak to strong); the HIGH/MEDIUM risk verdict comes later, from scoring.
def strongest(result):
    return max((s.severity for s in result.signals), default=0)


def test_every_demo_email_is_delivered_and_scored():
    assert set(RESULTS) == set(SCENARIO)


def test_detection_sees_original_links_not_tracking_links():
    for delivered, message, _ in RESULTS.values():
        assert delivered.links or not delivered.urls
        assert "/r/" not in " ".join(link.url for link in message.urls)
        assert {link.url for link in message.urls} >= set(delivered.urls)


def test_campaign_is_high_or_above_on_delivery():
    campaign = [r for i, r in RESULTS.items() if SCENARIO[i].campaign_id == "camp-ms-verify"]
    assert len(campaign) == 14
    assert all(strongest(result) >= 3 for _, _, result in campaign)


def test_legitimate_mail_has_no_strong_signal_on_delivery():
    for email_id, (_, _, result) in RESULTS.items():
        if SCENARIO[email_id].label == "legitimate" and email_id != AMBIGUOUS:
            assert strongest(result) < 2, email_id


def test_ambiguous_mail_is_medium_on_delivery():
    _, _, result = RESULTS[AMBIGUOUS]
    assert strongest(result) == 2
    assert SignalCategory.CREDENTIAL_REQUEST in {s.category for s in result.signals}
