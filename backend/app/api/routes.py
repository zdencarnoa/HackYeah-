from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import IncidentRow
from app.db.seed import seed_minimal
from app.db.session import get_db, reset_db
from app.campaigns import correlation
from app.campaigns.ingest import UnknownRecipient, ingest_message
from app.db.models import CampaignRow
from app.incidents import service
from app.schemas_proposal import (
    Campaign, Evidence, Incident, Interaction, InteractionResult, MessageIn, PubSubPush,
)

router = APIRouter()


@router.post("/api/evidence", response_model=Incident | None)
def post_evidence(ev: Evidence, db: Session = Depends(get_db)):
    """Intake for A (link click), D (unusual sign-in), B (email_scored)."""
    return service.add_evidence(db, ev)


@router.post("/api/integrations/chrome/password-reuse")
def chrome_password_reuse(push: PubSubPush, db: Session = Depends(get_db)):
    return service.handle_password_reuse(db, push)


@router.post("/api/interactions", response_model=InteractionResult)
def post_interaction(it: Interaction, db: Session = Depends(get_db)):
    return service.record_interaction(db, it)


@router.get("/api/incidents", response_model=list[Incident])
def get_incidents(db: Session = Depends(get_db)):
    return service.list_incidents(db)


@router.get("/api/incidents/{incident_id}", response_model=Incident)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    row = db.get(IncidentRow, incident_id)
    if not row:
        raise HTTPException(404, "incident not found")
    return service.to_incident(db, row)


@router.post("/api/messages/ingest", response_model=Campaign | None)
def post_message(msg: MessageIn, db: Session = Depends(get_db)):
    """Called by D's mailbox on every delivery, after A's rewriting and B's scoring."""
    try:
        return ingest_message(db, msg)
    except UnknownRecipient as e:
        raise HTTPException(422, f"unknown recipient: {e}")


@router.get("/api/campaigns", response_model=list[Campaign])
def get_campaigns(db: Session = Depends(get_db)):
    return correlation.list_campaigns(db)


@router.get("/api/campaigns/{campaign_id}", response_model=Campaign)
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    row = db.get(CampaignRow, campaign_id)
    if not row:
        raise HTTPException(404, "campaign not found")
    return correlation.campaign_out(db, row)


@router.post("/api/dev/reset-and-seed")
def dev_reset_and_seed(db: Session = Depends(get_db)):
    """DEV ONLY. Replace with D's /api/sim/reset once the real org exists."""
    reset_db()
    seed_minimal(db)
    return {"ok": True}
