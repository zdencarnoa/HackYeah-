"""Generate frontend/src/mocks/*.json from the real backend.

D's demo data goes through A's detection and B's analyze(), so the UI is built
against real Message and Assessment objects, not hand-written ones. Run it from a
checkout where A's, B's and D's work is merged (B's risk_scoring branch has all three):

    PYTHONPATH=<checkout>/backend python frontend/scripts/generate_mocks.py <checkout>

Campaigns are a stand-in for C's correlation until C's API exists. The scenario
labels in D's data are used only for that grouping, never shown as a verdict.
"""

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.detection import message_from_sim
from app.scoring.analyze import analyze
from app.simulation.seed import load_approved_logins, load_emails, load_org

OUT_DIR = Path(__file__).resolve().parents[1] / "src" / "mocks"
DEMO_START = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


def main(checkout: Path) -> None:
    org = load_org()
    by_email = {e.email: e for e in org.employees}
    everyone = f"all@{org.domain}"

    emails = []
    for sim in load_emails():
        recipients = [e.id for e in org.employees] if everyone in sim.to else [by_email[a].id for a in sim.to]
        message = message_from_sim(sim, DEMO_START + timedelta(seconds=sim.deliver_offset_s))
        emails.append({
            "id": sim.id,
            "deliver_offset_s": sim.deliver_offset_s,
            "recipient_ids": recipients,
            "message": message.model_dump(mode="json"),
            "assessment": analyze(message).model_dump(mode="json"),
        })

    campaigns = {}
    for sim in load_emails():
        if sim.scenario.campaign_id:
            campaigns.setdefault(sim.scenario.campaign_id, []).append(sim)

    write("org.json", {
        "name": org.name,
        "domain": org.domain,
        "employees": [e.model_dump(mode="json") for e in org.employees],
        "services": [s.model_dump(mode="json") for s in org.services],
        "dependencies": [d.model_dump(mode="json") for d in org.dependencies],
        "approved_logins": [a.model_dump(mode="json") for a in load_approved_logins()],
    })
    write("mail.json", {
        "generated_from": _revision(checkout),
        "demo_start": DEMO_START.isoformat(),
        "emails": emails,
    })
    write("campaigns.json", [_campaign(cid, sims, by_email) for cid, sims in campaigns.items()])
    print(f"Wrote {len(emails)} emails and {len(campaigns)} campaign(s) to {OUT_DIR}")


def _campaign(campaign_id: str, sims, by_email) -> dict:
    """What C's correlation would return: shared traits in plain language."""
    recipients = list(dict.fromkeys(a for sim in sims for a in sim.to))
    departments = list(dict.fromkeys(str(by_email[a].department) for a in recipients))
    sender_domains = {sim.sender_address.rsplit("@", 1)[1] for sim in sims}
    hosts = {url.split("/")[2] for sim in sims for url in sim.urls}
    offsets = [sim.deliver_offset_s for sim in sims]
    traits = []
    if len(sender_domains) == 1:
        traits.append(f"Same sender domain: all {len(sims)} messages come from {next(iter(sender_domains))}")
    if len(hosts) == 1:
        traits.append(f"Same destination: every link leads to {next(iter(hosts))}")
    traits.append("Similar wording: account suspension and identity verification")
    traits.append(f"Delivered in two waves within {round((max(offsets) - min(offsets)) / 60)} minutes")
    return {
        "id": campaign_id,
        "name": "Microsoft Account Verification" if "ms" in campaign_id else campaign_id,
        "message_ids": [sim.id for sim in sims],
        "recipients": recipients,
        "departments": departments,
        "shared_traits": traits,
        "updated_at": (DEMO_START + timedelta(seconds=max(offsets))).isoformat(),
    }


def _revision(checkout: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(checkout), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def write(name: str, data) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd())
