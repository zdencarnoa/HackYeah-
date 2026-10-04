"""Render D's SimEmail demo messages as .eml, so demo mail enters detection
through parse_eml exactly like an uploaded file."""

from datetime import UTC, datetime
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import format_datetime

from app.detection.ingest import parse_eml
from app.schemas import Message, SimEmail

# The dataset only has attachment names, types and sizes, so bodies are filler.
PLACEHOLDER = b"SIMULATED ATTACHMENT. The demo dataset has no file content.\n"


def message_from_sim(sim: SimEmail, delivered_at: datetime | None = None) -> Message:
    """Parse a demo message as if it were uploaded, keeping D's id so every
    component refers to it by the same key."""
    return parse_eml(render_eml(sim, delivered_at)).model_copy(update={"id": sim.id})


def render_eml(sim: SimEmail, delivered_at: datetime | None = None) -> bytes:
    """The .eml that the receiving mail server would have stored.

    Ground truth (sim.scenario) and delivery scheduling are never written. The
    same SimEmail and delivered_at always give the same bytes.
    """
    sender_domain = sim.sender_address.rsplit("@", 1)[1]
    mx = "mx." + sim.to[0].rsplit("@", 1)[1]
    date = format_datetime(delivered_at or datetime.now(UTC))
    dkim = f"dkim={sim.auth.dkim}" + (f" header.d={sender_domain}" if sim.auth.dkim != "none" else "")

    msg = EmailMessage()
    msg["Received"] = f"from {sender_domain} ([{sim.sending_ip}]) by {mx} with ESMTPS; {date}"
    msg["Authentication-Results"] = (f"{mx}; spf={sim.auth.spf} smtp.mailfrom={sender_domain}; "
                                     f"{dkim}; dmarc={sim.auth.dmarc} header.from={sender_domain}")
    msg["From"] = Address(display_name=sim.sender_name, addr_spec=sim.sender_address)
    msg["To"] = ", ".join(sim.to)
    if sim.cc:
        msg["Cc"] = ", ".join(sim.cc)
    if sim.reply_to:
        msg["Reply-To"] = sim.reply_to
    msg["Subject"] = sim.subject
    msg["Date"] = date
    msg["Message-ID"] = f"<{sim.id}@{sender_domain}>"

    msg.set_content(sim.body_text)
    if sim.body_html:
        msg.add_alternative(sim.body_html, subtype="html")
    for attachment in sim.attachments:
        maintype, _, subtype = attachment.content_type.partition("/")
        msg.add_attachment(_filler(attachment.size_bytes), maintype=maintype, subtype=subtype,
                           filename=attachment.filename)
    # Fixed MIME boundaries instead of random ones keep the output reproducible.
    for i, part in enumerate([p for p in msg.walk() if p.is_multipart()]):
        part.set_boundary(f"=_sim_{sim.id}_{i}")
    return msg.as_bytes()


def _filler(size: int) -> bytes:
    return (PLACEHOLDER * (size // len(PLACEHOLDER) + 1))[:size]
