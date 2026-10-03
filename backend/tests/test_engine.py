import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.schemas import SimEventType
from app.simulation.engine import AttackEngine
from app.simulation.events import EventBus
from app.simulation.seed import load_emails, load_org

ALICE = "e01"
AFTER_EVERYTHING = 10_000  # a demo second later than any delivery time


class FakeClock:
    """A clock the test moves by hand, so nothing has to really wait."""

    def __init__(self):
        self.current_time = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)

    def __call__(self):
        return self.current_time

    def advance(self, seconds: float):
        self.current_time += timedelta(seconds=seconds)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def event_bus(clock):
    return EventBus(get_current_time=clock)


@pytest.fixture
def engine(event_bus, clock):
    return AttackEngine(event_bus, get_current_time=clock, public_base_url="http://sim.test")


def test_delivers_only_what_is_due(engine):
    due_ids = [email.id for email in load_emails() if email.deliver_after_seconds <= 130]
    delivered = engine.jump_to_demo_second(130)
    assert [email.id for email in delivered] == due_ids
    assert engine.status().delivered_count == len(due_ids)


def test_ground_truth_never_leaves_the_engine(engine):
    received_by_ingestion = []
    engine.on_deliver = received_by_ingestion.append
    engine.jump_to_demo_second(AFTER_EVERYTHING)
    assert len(received_by_ingestion) == 39
    for delivered_email in received_by_ingestion:
        fields = delivered_email.model_dump()
        assert "scenario" not in fields and "deliver_after_seconds" not in fields


def test_all_company_mail_expands_to_every_employee(engine):
    engine.jump_to_demo_second(AFTER_EVERYTHING)
    assert len(engine.delivered_emails_by_id["leg-03"].recipient_ids) == len(load_org().employees)
    assert all("leg-03" in message_ids for message_ids in engine.inbox_message_ids_by_employee.values())


def test_inbox_links_are_rewritten_per_recipient(engine):
    engine.jump_to_demo_second(AFTER_EVERYTHING)
    alice_campaign_email = next(message for message in engine.inbox(ALICE) if message.id == "cmp-01")
    original_url = engine.delivered_emails_by_id["cmp-01"].urls[0]
    assert original_url not in alice_campaign_email.body_text
    [tracked_link] = alice_campaign_email.links
    assert f"http://sim.test/r/{tracked_link.token}" in alice_campaign_email.body_text
    assert tracked_link.employee_id == ALICE and tracked_link.url == original_url


def test_each_recipient_gets_their_own_token(engine):
    engine.jump_to_demo_second(AFTER_EVERYTHING)
    tokens = [link.token for link in engine.delivered_emails_by_id["leg-06"].links]
    assert len(tokens) == len(set(tokens)) == len(load_org().employees)


def test_click_records_event_and_unknown_token_is_ignored(engine, event_bus):
    engine.jump_to_demo_second(120)
    [tracked_link] = engine.delivered_emails_by_id["cmp-01"].links
    assert engine.record_click(tracked_link.token) == tracked_link
    click_event = event_bus.event_history[-1]
    assert click_event.type == SimEventType.LINK_CLICKED
    assert click_event.employee_id == ALICE
    assert click_event.data["domain"] == "micr0soft-verify.example"
    assert engine.record_click("nope") is None


def test_failing_ingestion_hook_does_not_stop_delivery(engine):
    def broken_ingestion(delivered_email):
        raise RuntimeError("ingestion is down")

    engine.on_deliver = broken_ingestion
    assert len(engine.jump_to_demo_second(AFTER_EVERYTHING)) == 39


def test_step_delivers_next_message_and_moves_timeline(engine):
    first_email = load_emails()[0]
    [delivered] = engine.step()
    assert delivered.id == first_email.id
    assert engine.demo_seconds_elapsed() == first_email.deliver_after_seconds


def test_reset_clears_deliveries(engine):
    engine.jump_to_demo_second(AFTER_EVERYTHING)
    engine.reset()
    status = engine.status()
    assert status.delivered_count == 0 and status.demo_seconds_elapsed == 0
    assert not engine.tracked_links_by_token
    assert all(not message_ids for message_ids in engine.inbox_message_ids_by_employee.values())


def test_running_timeline_uses_speed(engine, clock):
    async def scenario():
        engine.start(speed=10)
        clock.advance(12)  # 12 real seconds at 10x = 120 demo seconds
        await asyncio.sleep(0)
        assert engine.demo_seconds_elapsed() == 120
        engine.deliver_due_emails()
        assert "cmp-01" in engine.delivered_emails_by_id
        engine.pause()
        clock.advance(100)
        assert engine.demo_seconds_elapsed() == 120 and not engine.is_running

    asyncio.run(scenario())


def test_full_run_finishes_with_real_clock():
    engine = AttackEngine(EventBus())

    async def scenario():
        engine.start(speed=1000)
        while engine.is_running:
            await asyncio.sleep(0.01)

    asyncio.run(asyncio.wait_for(scenario(), timeout=5))
    assert engine.status().delivered_count == 39 and engine.is_finished


def test_http_flow():
    from app.simulation.dev_app import app
    from app.simulation.runtime import engine, reset_demo

    reset_demo()
    client = TestClient(app)
    while "cmp-01" not in engine.delivered_emails_by_id:
        assert client.post("/api/sim/attack/control/step").status_code == 200

    [alice_message] = [m for m in client.get(f"/api/sim/inbox/{ALICE}").json() if m["id"] == "cmp-01"]
    token = alice_message["links"][0]["token"]
    # A phishing link shows the fake login page inline (not a redirect).
    response = client.get(f"/r/{token}", follow_redirects=False)
    assert response.status_code == 200
    assert "SIMULATION" in response.text

    legit_message = next(m for m in client.get("/api/sim/inbox/e09").json() if m["id"] == "leg-04")
    response = client.get(f"/r/{legit_message['links'][0]['token']}", follow_redirects=False)
    assert response.headers["location"].startswith("/sim/external?url=")

    assert client.get("/r/unknown").status_code == 404
    assert client.get("/api/sim/inbox/nobody").status_code == 404
    reset_demo()
