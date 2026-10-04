"""Seed C's database with D's synthetic organization.

C's db/seed.py ships a placeholder org; this loads the real one from
data/org.json, so ingestion can resolve every demo recipient by id or email.
"""

from sqlalchemy.orm import Session

from app.db.models import EmployeeRow
from app.simulation.seed import load_org


def seed_org(db: Session) -> int:
    """Insert every employee from data/org.json. Returns how many were added."""
    org = load_org()
    db.add_all(
        EmployeeRow(id=e.id, name=e.name, email=e.email, department=e.department.value)
        for e in org.employees
    )
    db.commit()
    return len(org.employees)
