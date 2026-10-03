"""Write every demo message to data/eml/<id>.eml for the "Is this safe?" upload.

Run from backend/: python -m app.detection.export_eml

The files are generated and gitignored. data/emails/*.json stays the source of truth.
"""

from datetime import UTC, datetime, timedelta

from app.detection.sim_eml import render_eml
from app.simulation.seed import DATA_DIR, load_emails

OUT_DIR = DATA_DIR / "eml"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    for stale in OUT_DIR.glob("*.eml"):
        stale.unlink()
    start = datetime.now(UTC).replace(microsecond=0)
    emails = load_emails()
    for sim in emails:
        delivered_at = start + timedelta(seconds=sim.deliver_offset_s)
        (OUT_DIR / f"{sim.id}.eml").write_bytes(render_eml(sim, delivered_at))
    print(f"Wrote {len(emails)} .eml files to {OUT_DIR}")


if __name__ == "__main__":
    main()
