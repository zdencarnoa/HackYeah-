"""Delivery pipeline (D1): score every delivered email and record it.

This is the glue that turns the attack into live detection. For each message the
attack engine delivers, it:

  1. renders the original email to A's `Message` (`message_from_sim`),
  2. scores it to a risk level with A's rules and B's fusion, and
  3. hands it to C's `ingest_message()`, which stores it, files `email_scored`
     evidence and runs campaign correlation.

So detection does not depend on the employee: every delivered email is scored on
arrival. Scoring here stops at the risk level and skips B's LLM explanation; the
full Assessment with its plain-language reasons is produced on demand when the
employee opens "Is this safe?" (B's /api/analyze), not on every delivery. The
engine already runs `on_deliver` inside a try/except, so a failure here is logged
and never stops delivery.
"""

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.campaigns.ingest import UnknownRecipient, ingest_message
from app.detection import detect
from app.detection.sim_eml import message_from_sim
from app.incidents.service import add_evidence, handle_password_reuse
from app.schemas import (
    DeliveredEmail,
    Evidence,
    MessageIn,
    PasswordReuseEvent,
    PubSubPush,
    Severity,
    SimEvent,
    SimEventType,
)
from app.scoring.fusion import fuse
from app.scoring.ml_signal import classify, ml_signal
from app.simulation.credentials import CredentialSimulator, to_pubsub_push
from app.simulation.engine import AttackEngine

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


class DeliveryPipeline:
    """Callable used as `engine.on_deliver`. Scores a delivered email and ingests it.

    C's message store keys on the message id with a single recipient, so one row is
    written per delivered email, to its primary recipient. Demo campaign messages
    are one-to-one, so this is exact for them; broadcast (`all@`) mail is LOW risk
    and does not drive incidents, so attributing it to the first recipient is fine.
    """

    def __init__(self, engine: AttackEngine, session_factory: SessionFactory, use_ml: bool = True):
        self.engine = engine
        self.session_factory = session_factory
        self.use_ml = use_ml

    def score(self, delivered: DeliveredEmail) -> Severity | None:
        """Risk level for a delivered email, the fast way: rules + fusion, no LLM."""
        sim_email = self.engine.sim_email_by_id.get(delivered.id)
        if sim_email is None:
            logger.warning("no source email for %s; cannot score", delivered.id)
            return None
        message = message_from_sim(sim_email, delivered.delivered_at)
        signals = list(detect(message).signals)
        if self.use_ml and (sig := ml_signal(classify(message))) is not None:
            signals.append(sig)
        return fuse(signals).risk

    def __call__(self, delivered: DeliveredEmail) -> None:
        risk = self.score(delivered)
        if risk is None or not delivered.recipient_ids:
            return
        recipient_id = delivered.recipient_ids[0]
        message_in = MessageIn(
            id=delivered.id,
            sender=delivered.sender_address,
            recipient=recipient_id,
            subject=delivered.subject,
            body=delivered.body_text,
            urls=list(delivered.urls),
            received_at=delivered.delivered_at,
            risk=risk,
        )
        with self.session_factory() as db:
            try:
                ingest_message(db, message_in)
            except UnknownRecipient:
                logger.warning("ingest: unknown recipient %s for %s", recipient_id, delivered.id)


def attach(engine: AttackEngine, session_factory: SessionFactory, use_ml: bool = True) -> DeliveryPipeline:
    """Make the engine score and ingest on delivery. Returns the pipeline."""
    pipeline = DeliveryPipeline(engine, session_factory, use_ml=use_ml)
    engine.on_deliver = pipeline
    return pipeline


def attach_credentials(credentials: CredentialSimulator, session_factory: SessionFactory) -> Callable[[], None]:
    """D2: feed the simulator's credential events into C's incident system.

    When a password is entered on a phishing page, the simulator produces a
    Chrome-style PASSWORD_REUSE_EVENT; we hand it to C's `handle_password_reuse`
    through the same Pub/Sub shape its HTTP endpoint receives (a real Chrome feed
    would POST that over the network). The follow-up unusual sign-in is filed as
    `unusual_signin` evidence so it joins the incident timeline.
    """

    def on_password_reuse(event: PasswordReuseEvent) -> None:
        push = PubSubPush.model_validate(to_pubsub_push(event))
        with session_factory() as db:
            handle_password_reuse(db, push)

    def on_sim_event(event: SimEvent) -> None:
        if event.type is SimEventType.UNUSUAL_SIGN_IN and event.employee_id:
            with session_factory() as db:
                add_evidence(db, Evidence(
                    kind="unusual_signin", employee_id=event.employee_id,
                    source="automatic", timestamp=event.at))

    credentials.on_password_reuse = on_password_reuse
    return credentials.event_bus.subscribe(on_sim_event)  # unsubscribe handle


def wire_live(engine, credentials, containment, session_factory: SessionFactory,
              use_ml: bool = False) -> Callable[[], None]:
    """D5: wire all three bridges onto the live simulation objects at app startup.

    Returns an `unwire()` that restores the previous hooks, so a shared runtime
    stays clean (used on app shutdown and between tests).
    """
    previous = (engine.on_deliver, credentials.on_password_reuse, containment.on_contained)
    attach(engine, session_factory, use_ml=use_ml)
    unsubscribe = attach_credentials(credentials, session_factory)
    attach_containment(containment, session_factory)

    def unwire() -> None:
        engine.on_deliver, credentials.on_password_reuse, containment.on_contained = previous
        unsubscribe()

    return unwire


def reset_all(session_factory: SessionFactory) -> None:
    """D3: one call restores the whole demo for a rehearsal.

    Resets D's in-memory state (engine, credentials, containment, recovery) and
    C's database (messages, incidents, evidence, campaigns), then re-seeds the
    organization so ingestion can resolve recipients again.
    """
    from app.db.session import reset_db
    from app.simulation import runtime
    from app.simulation.org_seed import seed_org

    runtime.reset_demo()  # D's state + a DEMO_RESET event
    reset_db()            # drop and recreate C's tables
    with session_factory() as db:
        seed_org(db)


def mark_incidents_contained(db, employee_ids: list[str], message_ids: list[str]) -> list[str]:
    """Set the open incidents touched by a containment to "contained" and announce it.

    An incident is touched if it belongs to a contained message's campaign, or if it
    holds evidence for one of the contained (affected) employees. Returns their ids.
    """
    from sqlalchemy import select

    from app.api import events
    from app.db.models import EvidenceRow, IncidentRow, MessageRow

    incidents: dict[str, IncidentRow] = {}
    if message_ids:
        campaign_ids = set(db.scalars(
            select(MessageRow.campaign_id).where(
                MessageRow.id.in_(message_ids), MessageRow.campaign_id.is_not(None))
        ).all())
        if campaign_ids:
            for inc in db.scalars(select(IncidentRow).where(
                    IncidentRow.campaign_id.in_(campaign_ids), IncidentRow.status == "open")).all():
                incidents[inc.id] = inc
    if employee_ids:
        for inc in db.scalars(
            select(IncidentRow).join(EvidenceRow, EvidenceRow.incident_id == IncidentRow.id).where(
                EvidenceRow.employee_id.in_(employee_ids), IncidentRow.status == "open")
        ).all():
            incidents[inc.id] = inc

    for inc in incidents.values():
        inc.status = "contained"
    db.commit()
    for inc_id in incidents:
        events.publish("containment.done", {"incident_id": inc_id, "status": "contained"})
    return list(incidents)


def attach_containment(containment, session_factory: SessionFactory) -> None:
    """D4: when a campaign is contained, mark its incident contained in C's database."""

    def on_contained(request, results) -> None:
        with session_factory() as db:
            mark_incidents_contained(db, list(request.employee_ids), list(request.message_ids))

    containment.on_contained = on_contained
