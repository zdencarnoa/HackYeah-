from __future__ import annotations

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.db.models import CampaignRow, ChecklistRow, EvidenceRow, IncidentRow
from app.schemas_proposal import Dashboard, Severity


def build_dashboard(db: Session) -> Dashboard:
    open_incs = db.scalars(select(IncidentRow).where(IncidentRow.status == "open")
                           .order_by(IncidentRow.created_at.desc())).all()
    ids = [i.id for i in open_incs]
    by_sev = {s.name: 0 for s in Severity}
    for i in open_incs:
        by_sev[Severity(i.severity).name] += 1
    items = db.scalars(select(ChecklistRow).where(ChecklistRow.incident_id.in_(ids))).all() if ids else []
    affected = db.scalar(select(func.count(distinct(EvidenceRow.employee_id)))
                         .where(EvidenceRow.incident_id.in_(ids))) if ids else 0
    return Dashboard(
        open_incidents=len(open_incs),
        by_severity=by_sev,
        active_campaigns=db.scalar(select(func.count()).select_from(CampaignRow)) or 0,
        affected_employees=affected or 0,
        pending_approvals=sum(1 for c in items if c.needs_approval and c.approved_by is None and not c.done),
        checklist_done=sum(1 for c in items if c.done),
        checklist_total=len(items),
        latest_critical_incident_id=next(
            (i.id for i in open_incs if i.severity == int(Severity.CRITICAL)), None),
    )
