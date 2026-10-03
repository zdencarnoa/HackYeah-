"""Tests for blast radius, credentials, containment, recovery and the demo flow."""

from datetime import UTC, datetime, timedelta

import pytest

from app.schemas import ContainmentActionType as Action
from app.schemas import ContainmentRequest, SimEventType
from app.simulation.blast_radius import compute_blast_radius
from app.simulation.containment import ContainmentService
from app.simulation.credentials import CredentialSimulator, to_pubsub_push
from app.simulation.engine import AttackEngine
from app.simulation.events import EventBus
from app.simulation.recovery import RecoveryTracker
from app.simulation.seed import load_approved_logins, load_org

ALICE = "e01"
ADMIN = "e15"  # Oliver Martin, IT admin
CAMPAIGN = "camp-ms-verify"
PHISH_DOMAIN = "micr0soft-verify.example"


class FakeClock:
    def __init__(self):
        self.current_time = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)

    def __call__(self):
        return self.current_time

    def advance(self, seconds):
        self.current_time += timedelta(seconds=seconds)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def event_bus(clock):
    return EventBus(get_current_time=clock)


@pytest.fixture
def engine(event_bus, clock):
    engine = AttackEngine(event_bus, get_current_time=clock, public_base_url="http://sim.test")
    engine.jump_to_demo_second(10_000)  # deliver everything so containment has messages
    return engine


# --- blast radius -----------------------------------------------------------


def test_blast_radius_reaches_finance_services_for_alice():
    blast = compute_blast_radius(load_org(), ALICE)
    affected = set(blast.affected_service_ids)
    assert {"idp", "mail", "files", "erp"} <= affected  # Finance access
    assert "hr_portal" not in affected  # HR app she cannot reach
    assert "invoices_data" in affected  # data behind the ERP she can reach
    assert "payroll_data" not in affected
    reached = {node.id for node in blast.nodes if node.at_risk}
    assert "colleagues" in reached  # mailbox lets an attacker phish colleagues
    assert all(node.reason for node in blast.nodes)


def test_blast_radius_unknown_employee():
    with pytest.raises(KeyError):
        compute_blast_radius(load_org(), "nobody")


# --- credentials ------------------------------------------------------------


def test_password_on_unapproved_domain_fires_event_and_sign_in(event_bus):
    credentials = CredentialSimulator(event_bus, unusual_sign_in_delay_seconds=0)
    event = credentials.record_password_entry(ALICE, f"https://{PHISH_DOMAIN}/verify", message_id="cmp-01")
    assert event is not None and event.domain == PHISH_DOMAIN
    assert "password" not in event.model_dump()  # never carries the password
    types = [e.type for e in event_bus.event_history]
    assert SimEventType.PASSWORD_REUSE in types
    assert SimEventType.UNUSUAL_SIGN_IN in types  # fired immediately with no running loop


def test_password_on_approved_domain_fires_nothing(event_bus):
    credentials = CredentialSimulator(event_bus)
    approved = load_approved_logins()[0].domain
    assert credentials.record_password_entry(ALICE, f"https://{approved}/login") is None
    assert not event_bus.event_history


def test_pubsub_wrapper_round_trips(event_bus):
    import base64
    import json

    credentials = CredentialSimulator(event_bus, unusual_sign_in_delay_seconds=0)
    event = credentials.record_password_entry(ALICE, f"https://{PHISH_DOMAIN}/verify")
    push = to_pubsub_push(event)
    decoded = json.loads(base64.b64decode(push["message"]["data"]))
    assert decoded["domain"] == PHISH_DOMAIN and decoded["simulated"] is True


# --- containment ------------------------------------------------------------


def _campaign_message_ids(engine):
    return [m.id for m in engine.delivered_emails_by_id.values() if m.id.startswith("cmp-")]


def test_containment_requires_admin_approval(engine, event_bus):
    service = ContainmentService(engine, event_bus)
    request = ContainmentRequest(action=Action.QUARANTINE_MESSAGES, message_ids=["cmp-01"], approved_by=ALICE)
    with pytest.raises(PermissionError):
        service.apply(request)


def test_contain_campaign_bundle(engine, event_bus):
    service = ContainmentService(engine, event_bus)
    message_ids = _campaign_message_ids(engine)
    request = ContainmentRequest(
        action=Action.CONTAIN_CAMPAIGN,
        campaign_id=CAMPAIGN,
        message_ids=message_ids,
        employee_ids=[ALICE],
        approved_by=ADMIN,
    )
    results = service.apply(request)
    actions = {r.action for r in results}
    assert Action.QUARANTINE_MESSAGES in actions and Action.BLOCK_DOMAIN in actions
    assert all(r.simulated and r.approved_by == ADMIN for r in results)
    assert len(service.quarantined_message_ids) == 14
    assert PHISH_DOMAIN in service.blocked_domains
    assert service.is_message_contained(message_ids[0])
    assert ALICE in service.reset_credential_employee_ids


def test_block_domain_stops_future_deliveries(engine, event_bus):
    service = ContainmentService(engine, event_bus)
    service.apply(ContainmentRequest(
        action=Action.CONTAIN_CAMPAIGN, campaign_id=CAMPAIGN,
        message_ids=_campaign_message_ids(engine), approved_by=ADMIN,
    ))
    # Any campaign message, even one not named, is now contained by its blocked domain.
    assert all(service.is_message_contained(m) for m in _campaign_message_ids(engine))


# --- recovery ---------------------------------------------------------------


def test_recovery_progresses_after_containment(engine, event_bus):
    service = ContainmentService(engine, event_bus)
    tracker = RecoveryTracker(service)
    assert all(track.percent == 0 for track in tracker.status().tracks)

    service.apply(ContainmentRequest(
        action=Action.CONTAIN_CAMPAIGN, campaign_id=CAMPAIGN,
        message_ids=_campaign_message_ids(engine), employee_ids=[ALICE], approved_by=ADMIN,
    ))
    status = tracker.status()
    tracks = {track.name: track.percent for track in status.tracks}
    assert tracks["Message containment"] == 100
    assert tracks["Affected users notified"] == 100
    assert tracks["Account protection"] == 100  # Alice had sessions revoked and credentials reset

    remaining_ids = {item.id for item in status.remaining_actions}
    assert "complete_incident_report" in remaining_ids
    tracker.mark_done("review_account_activity")
    tracker.mark_done("confirm_password_reset")
    tracker.mark_done("complete_incident_report")
    assert {track.name: track.percent for track in tracker.status().tracks}["Investigation"] == 100
