"""DB side of campaign correlation. The matching rules live in matching.py (pure Python)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api import events
from app.db.models import CampaignRow, EmployeeRow, IncidentRow, MessageRow
from app.incidents.escalation import APPROVED_LOGINS
from app.incidents.service import as_utc, link_incidents_to_campaign
from app.schemas_proposal import Campaign, Severity

from .matching import JOIN_SCORE, MsgFeatures, campaign_name, features, pair_score, shared_traits

SUSPICIOUS = int(Severity.HIGH)  # only HIGH+ messages are clustered; LOW and MEDIUM never are


def _feat(m: MessageRow) -> MsgFeatures:
    return features(m.id, m.sender, m.subject, m.body, list(m.urls or []), as_utc(m.received_at),
                    ignore_hosts=frozenset(APPROVED_LOGINS))


def campaign_out(db: Session, row: CampaignRow) -> Campaign:
    msgs = db.scalars(select(MessageRow).where(MessageRow.campaign_id == row.id)
                      .order_by(MessageRow.received_at)).all()
    emps = {e.id: e for e in db.scalars(select(EmployeeRow).where(
        EmployeeRow.id.in_({m.recipient_id for m in msgs})))}
    return Campaign(
        id=row.id, name=row.name, message_ids=[m.id for m in msgs],
        recipients=sorted(emps), departments=sorted({e.department for e in emps.values()}),
        shared_traits=shared_traits([_feat(m) for m in msgs]),
        incident_id=db.scalar(select(IncidentRow.id).where(IncidentRow.campaign_id == row.id)),
        updated_at=as_utc(row.updated_at),
    )


def list_campaigns(db: Session) -> list[Campaign]:
    rows = db.scalars(select(CampaignRow).order_by(CampaignRow.created_at.desc())).all()
    return [campaign_out(db, r) for r in rows]


def correlate(db: Session, message_id: str) -> Campaign | None:
    """Join the message to a campaign (creating or merging as needed). Returns None when it
    matches nothing yet. A campaign always has at least two messages."""
    me = db.get(MessageRow, message_id)
    if me is None or me.risk is None or me.risk < SUSPICIOUS:
        return None
    mine = _feat(me)
    others = db.scalars(select(MessageRow).where(
        MessageRow.risk >= SUSPICIOUS, MessageRow.id != me.id)).all()
    matches = [o for o in others if pair_score(mine, _feat(o))[0] >= JOIN_SCORE]
    if not matches:
        row = db.get(CampaignRow, me.campaign_id) if me.campaign_id else None
        return campaign_out(db, row) if row else None

    ids = {o.campaign_id for o in matches if o.campaign_id}
    if me.campaign_id:
        ids.add(me.campaign_id)
    if ids:  # keep the oldest campaign, fold the others into it
        camps = sorted(db.scalars(select(CampaignRow).where(CampaignRow.id.in_(ids))).all(),
                       key=lambda c: as_utc(c.created_at))
        target, merged = camps[0], camps[1:]
    else:
        target, merged = CampaignRow(), []
        db.add(target)
        db.flush()
    for old in merged:
        db.execute(update(MessageRow).where(MessageRow.campaign_id == old.id)
                   .values(campaign_id=target.id))
        db.execute(update(IncidentRow).where(IncidentRow.campaign_id == old.id)
                   .values(campaign_id=target.id))
        db.delete(old)
    me.campaign_id = target.id
    for o in matches:
        o.campaign_id = target.id
    db.flush()

    members = db.scalars(select(MessageRow).where(MessageRow.campaign_id == target.id)).all()
    target.name = campaign_name([_feat(m) for m in members])
    target.updated_at = datetime.now(timezone.utc)
    db.commit()

    link_incidents_to_campaign(db, target.id)
    out = campaign_out(db, target)
    events.publish("campaign.updated", out.model_dump(mode="json"))
    return out
