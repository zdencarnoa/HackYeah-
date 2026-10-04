from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import IncidentRow
from app.db.seed import seed_minimal
from app.db.session import get_db, reset_db
from app.campaigns import correlation
from app.campaigns.ingest import UnknownRecipient, ingest_message
from app.db.models import CampaignRow
from app.incidents import ai_hooks, checklist, service
from app.incidents.dashboard import build_dashboard
from app.schemas import (
    ApproveBody, Campaign, CompleteBody, Dashboard, Evidence, Incident, Interaction,
    InteractionResult, MessageIn, PubSubPush, RecoveryProgress, TextResult,
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


def _checklist_call(fn, *args):
    try:
        return fn(*args)
    except service.ChecklistError as e:
        raise HTTPException(e.status, e.message)


def _incident_or_404(db: Session, incident_id: str):
    row = db.get(IncidentRow, incident_id)
    if not row:
        raise HTTPException(404, "incident not found")
    return service.to_incident(db, row)


@router.post("/api/checklist/{item_id}/approve", response_model=Incident)
def approve_step(item_id: str, body: ApproveBody = ApproveBody(), db: Session = Depends(get_db)):
    """Admin approves one containment step. D then runs the simulated action and calls /complete."""
    return _checklist_call(service.approve_item, db, item_id, body.approved_by)


@router.post("/api/checklist/{item_id}/complete", response_model=Incident)
def complete_step(item_id: str, body: CompleteBody = CompleteBody(), db: Session = Depends(get_db)):
    """Mark a step done. Containment steps answer 409 until approved."""
    return _checklist_call(service.complete_item, db, item_id, body.done)


@router.post("/api/incidents/{incident_id}/approve-all", response_model=Incident)
def approve_all_steps(incident_id: str, body: ApproveBody = ApproveBody(), db: Session = Depends(get_db)):
    """The 'Contain campaign' button: approve every pending containment step of the incident."""
    return _checklist_call(service.approve_all, db, incident_id, body.approved_by)


@router.get("/api/incidents/{incident_id}/progress", response_model=RecoveryProgress)
def get_progress(incident_id: str, db: Session = Depends(get_db)):
    _incident_or_404(db, incident_id)
    return checklist.progress(db, incident_id)


@router.get("/api/incidents/{incident_id}/summary", response_model=TextResult)
def get_summary(incident_id: str, db: Session = Depends(get_db)):
    text, source = ai_hooks.incident_summary(_incident_or_404(db, incident_id))
    return TextResult(text=text, source=source)


@router.get("/api/incidents/{incident_id}/notification/{employee_id}", response_model=TextResult)
def get_notification(incident_id: str, employee_id: str, db: Session = Depends(get_db)):
    inc = _incident_or_404(db, incident_id)
    if employee_id not in inc.affected_employees:
        raise HTTPException(404, "employee is not part of this incident")
    text, source = ai_hooks.employee_notification(inc, employee_id)
    return TextResult(text=text, source=source)


@router.get("/api/dashboard", response_model=Dashboard)
def get_dashboard(db: Session = Depends(get_db)):
    return build_dashboard(db)


@router.post("/api/dev/reset-and-seed")
def dev_reset_and_seed(db: Session = Depends(get_db)):
    """DEV ONLY. Replace with D's /api/sim/reset once the real org exists."""
    reset_db()
    seed_minimal(db)
    return {"ok": True}
