"""DEV placeholder for D's demo dataset. Plain dicts, usable from tests and scripts."""
from datetime import datetime, timedelta, timezone

RECIPIENTS = ["alice", "dan", "bob", "erin", "frank", "hank", "ida"]  # 7 people, 3 departments
SENDERS = [
    "security@micr0soft-verify.example",
    "no-reply@micr0soft-verify.example",
    "account-team@mail.micr0soft-verify.example",
]
SUBJECTS = [
    "URGENT: Your account will be suspended",
    "Action required: verify your Microsoft account",
    "Security alert: unusual activity on your account",
]
BODIES = [
    "Dear {name}, we detected unusual activity on your Microsoft account. Your account will be "
    "suspended within 24 hours unless you verify your password immediately. Verify now: {url} "
    "If you ignore this message your account will be permanently closed. Microsoft Account Security Team",
    "Hello {name}, unusual activity was detected on your Microsoft account. Your account will be "
    "suspended within 24 hours unless you verify your password immediately. Verify now: {url} "
    "If you ignore this notice your account will be permanently closed. Microsoft Account Security Team",
    "Dear {name}, we noticed unusual sign-in activity on your Microsoft account. Your account will be "
    "suspended within 24 hours unless you confirm your password immediately. Confirm now: {url} "
    "Ignoring this message will result in your account being permanently closed. Microsoft Account Security Team",
]


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def campaign_messages(count: int = 14, start: datetime | None = None) -> list[dict]:
    """Microsoft campaign variants m1..m{count}; m1-m3 are wave 1."""
    base = start or datetime.now(timezone.utc)
    out = []
    for i in range(count):
        who = RECIPIENTS[i % len(RECIPIENTS)]
        url = f"https://micr0soft-verify.example/login?id={i + 1}"
        out.append({
            "id": f"m{i + 1}",
            "sender": SENDERS[i % 3],
            "recipient": f"{who}@company.example",
            "subject": SUBJECTS[i % 3],
            "body": BODIES[i % 3].format(name=who.capitalize(), url=url),
            "urls": [url],
            "received_at": _iso(base + timedelta(seconds=20 * i)),
            "risk": 2,
        })
    return out


def invoice_fraud_messages(start: datetime | None = None) -> list[dict]:
    """Second, unrelated campaign: no links, different sender domain, different wording."""
    base = start or datetime.now(timezone.utc)
    return [{
        "id": f"i{n}",
        "sender": f"billing{n}@vendor-payments.example",
        "recipient": f"{who}@company.example",
        "subject": "Updated bank details for your next payment",
        "body": f"Hi {who.capitalize()}, our bank account has changed. Please send the next invoice "
                f"payment to the new IBAN in the attached form and confirm by reply. Thank you, Accounts {n}.",
        "urls": [],
        "received_at": _iso(base + timedelta(seconds=30 * n)),
        "risk": 2,
    } for n, who in enumerate(["erin", "dan", "hank"], start=1)]


def legit_invoice(start: datetime | None = None) -> dict:
    return {
        "id": "ok1", "sender": "billing@known-supplier.example", "recipient": "alice@company.example",
        "subject": "Invoice 2026/10 for September services",
        "body": "Hello Alice, please find our monthly invoice attached as agreed. Regards, Known Supplier.",
        "urls": [], "received_at": _iso(start or datetime.now(timezone.utc)), "risk": 0,
    }
