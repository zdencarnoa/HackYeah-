"""PLACEHOLDER seed so C can test alone. Person D's 25-employee org replaces this."""
from sqlalchemy.orm import Session

from .models import EmployeeRow

ORG = {
    "Finance": ["alice", "dan", "erin"],
    "HR": ["bob", "frank"],
    "Operations": ["hank", "ida"],
    "IT": ["carol", "gina"],
}


def seed_minimal(db: Session) -> None:
    db.add_all(
        EmployeeRow(id=e, name=e.capitalize(), email=f"{e}@company.example", department=dept)
        for dept, people in ORG.items() for e in people
    )
    db.commit()
