"""Load and validate the synthetic organization and demo mail from data/."""

import json
from functools import cache
from pathlib import Path

from pydantic import TypeAdapter

from app.schemas import ApprovedLogin, Organization, SimEmail

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
EMAIL_FILES = ["legitimate.json", "phishing_misc.json", "campaign_microsoft.json"]


def _read(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@cache
def load_org() -> Organization:
    return Organization.model_validate(_read(DATA_DIR / "org.json"))


@cache
def load_approved_logins() -> list[ApprovedLogin]:
    return TypeAdapter(list[ApprovedLogin]).validate_python(_read(DATA_DIR / "approved_logins.json"))


@cache
def load_emails() -> list[SimEmail]:
    """All demo messages, ordered by delivery time."""
    adapter = TypeAdapter(list[SimEmail])
    emails = [m for name in EMAIL_FILES for m in adapter.validate_python(_read(DATA_DIR / "emails" / name))]
    return sorted(emails, key=lambda m: m.deliver_after_seconds)
