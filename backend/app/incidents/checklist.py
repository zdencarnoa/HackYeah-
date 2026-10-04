from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChecklistRow, IncidentRow
from app.schemas import AreaProgress, RecoveryProgress

from .ai_hooks import checklist_reason
from .checklist_templates import AREAS, TEMPLATES


def sync_checklist(db: Session, inc: IncidentRow) -> bool:
    """Add the template items this incident's severity now calls for. Never removes or
    duplicates items. Does not commit. Returns True if something was added."""
    template = TEMPLATES.get(inc.type, TEMPLATES["suspicious_email"])
    have = set(db.scalars(select(ChecklistRow.key).where(ChecklistRow.incident_id == inc.id)))
    added = False
    for position, item in enumerate(template):
        if item.min_severity <= inc.severity and item.key not in have:
            db.add(ChecklistRow(
                incident_id=inc.id, key=item.key, position=position, action=item.action,
                rationale=checklist_reason(inc.type, item.key, item.rationale),
                area=item.area, needs_approval=item.needs_approval,
                containment_kind=item.containment_kind))
            added = True
    return added


def progress(db: Session, incident_id: str) -> RecoveryProgress:
    rows = db.scalars(select(ChecklistRow).where(ChecklistRow.incident_id == incident_id)
                      .order_by(ChecklistRow.position)).all()
    areas: dict[str, AreaProgress] = {}
    for area in AREAS:
        mine = [r for r in rows if r.area == area]
        if mine:
            done = sum(1 for r in mine if r.done)
            areas[area] = AreaProgress(done=done, total=len(mine), percent=round(100 * done / len(mine)))
    done_all = sum(1 for r in rows if r.done)
    return RecoveryProgress(
        incident_id=incident_id,
        percent=round(100 * done_all / len(rows)) if rows else 0,
        areas=areas,
        remaining=[r.action for r in rows if not r.done],
    )
