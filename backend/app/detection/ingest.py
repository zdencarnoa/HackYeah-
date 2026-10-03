"""Task 1: ingestion. Turns a raw .eml file into a Message.

Attachments are judged by name, type and size only. For a zip, the table of
contents is read in memory to see whether entries are encrypted. Nothing is
unpacked, written to disk or executed.
"""

import hashlib
import io
import logging
import re
import zipfile
from datetime import UTC, datetime
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import getaddresses, parsedate_to_datetime

from bs4 import BeautifulSoup

from app.schemas import Link, Message, MessageAttachment

log = logging.getLogger(__name__)

# Every real email has at least one of these. A file with none of them (a PDF,
# an image, a text note) is not an email.
EMAIL_HEADERS = {"from", "to", "subject", "date", "message-id"}
# Not preceded by a word character, "@" or ".", so "user@www.x.test" is no link.
TEXT_URL_RE = re.compile(r"(?<![\w@.])(?:https?://|www\.)[^\s<>\"')\]]+", re.IGNORECASE)
TRAILING_PUNCTUATION = ".,;:!?"
# Browsers drop tabs and newlines inside a URL, so attackers can hide behind them.
URL_WHITESPACE_RE = re.compile(r"[\t\r\n]")
BLOCK_TAGS = ["br", "p", "div", "li", "tr", "td", "th", "table", "blockquote",
              "h1", "h2", "h3", "h4", "h5", "h6"]


def parse_eml(raw: bytes) -> Message:
    """Parse an .eml file. Raises ValueError when the bytes are not an email."""
    msg = message_from_bytes(raw, policy=policy.default)
    headers = _headers(msg)
    if not {name.lower() for name, _ in headers} & EMAIL_HEADERS:
        raise ValueError("This file is not an email: it has no sender, recipient, subject or date.")

    sender_name, sender = _first_address(_all(headers, "From"))
    _, reply_to = _first_address(_all(headers, "Reply-To"))
    recipients = _addresses(_all(headers, "To") + _all(headers, "Cc"))

    text_part = msg.get_body(preferencelist=("plain",))
    html_part = msg.get_body(preferencelist=("html",))
    text = _content(text_part)
    html = _content(html_part) if html_part is not None else None
    if msg.get_content_maintype() == "multipart" and not msg.is_multipart():
        # A multipart with a missing or unused boundary has no parts. Scan the raw
        # body instead of nothing, so a malformed email cannot hide its links.
        text = msg.get_payload()

    return Message(
        id=_upload_id(_first(headers, "Message-ID"), recipients, raw),
        sender=sender,
        sender_name=sender_name,
        reply_to=reply_to or None,
        recipients=recipients,
        subject=_first(headers, "Subject") or "",
        body_text=text if text.strip() or not html else visible_text(html),
        body_html=html,
        urls=_dedupe(_links_from_html(html or "") + _links_from_text(text)),
        attachments=_attachments(msg, body_parts=(text_part, html_part)),
        headers=headers,
        received_at=_received_at(_first(headers, "Date")),
    )


def visible_text(html: str) -> str:
    """The text a reader sees in an HTML body, one block per line."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["head", "script", "style"]):
        tag.decompose()
    for tag in soup(BLOCK_TAGS):
        tag.insert_after("\n")
    lines = (" ".join(line.split()) for line in soup.get_text().splitlines())
    return "\n".join(line for line in lines if line)


def _headers(msg: EmailMessage) -> list[tuple[str, str]]:
    """Top-level headers, decoded and unfolded, with repeated headers kept in order."""
    headers = []
    for name, raw_value in msg.raw_items():
        try:
            value = str(msg.policy.header_fetch_parse(name, raw_value))
        except Exception:  # a malformed header keeps its raw text
            value = raw_value
        headers.append((name, " ".join(value.split())))
    return headers


def _all(headers: list[tuple[str, str]], name: str) -> list[str]:
    return [value for key, value in headers if key.lower() == name.lower()]


def _first(headers: list[tuple[str, str]], name: str) -> str | None:
    values = _all(headers, name)
    return values[0] if values else None


def _first_address(values: list[str]) -> tuple[str, str]:
    """(display name, lowercased address) of the first address, or ("", "")."""
    for name, address in getaddresses(values):
        if address:
            return name.strip(), address.strip().lower()
    return "", ""


def _addresses(values: list[str]) -> list[str]:
    found = []
    for _, address in getaddresses(values):
        address = address.strip().lower()
        if address and address not in found:
            found.append(address)
    return found


def _content(part: EmailMessage | None) -> str:
    if part is None:
        return ""
    try:
        return part.get_content()
    except Exception:  # broken charset or transfer encoding: decode leniently
        try:
            return (part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")
        except Exception:
            log.warning("could not decode a %s part", part.get_content_type())
            return ""


def _web_url(candidate: str) -> str | None:
    """The URL if it is a web link; None for mailto:, tel:, #anchors and relative paths."""
    url = URL_WHITESPACE_RE.sub("", candidate).strip()
    if url.lower().startswith(("http://", "https://")):
        return url
    if url.lower().startswith("www."):
        return "http://" + url
    return None


def _links_from_html(html: str) -> list[Link]:
    links = []
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        url = _web_url(a["href"])
        if url is None:
            continue
        # An image used as a button shows its alt text instead.
        text = a.get_text(" ").strip() or " ".join(img.get("alt", "") for img in a.find_all("img"))
        links.append(Link(url=url, anchor_text=" ".join(text.split()) or None, found_in="html"))
    return links


def _links_from_text(text: str) -> list[Link]:
    links = []
    for match in TEXT_URL_RE.finditer(text):
        url = _web_url(match.group().rstrip(TRAILING_PUNCTUATION))
        if url is not None:
            links.append(Link(url=url, found_in="text"))
    return links


def _dedupe(links: list[Link]) -> list[Link]:
    """One entry per (url, anchor text). A text link is dropped when the HTML part
    has the same URL, because the HTML entry also knows the anchor text."""
    html_urls = {link.url for link in links if link.found_in == "html"}
    seen, unique = set(), []
    for link in links:
        key = (link.url, link.anchor_text)
        if key in seen or (link.found_in == "text" and link.url in html_urls):
            continue
        seen.add(key)
        unique.append(link)
    return unique


def _leaf_parts(part: EmailMessage):
    """Non-multipart parts in document order. An attached email (message/rfc822)
    is one part; it is not opened."""
    if part.get_content_maintype() == "multipart":
        for sub in part.iter_parts():
            yield from _leaf_parts(sub)
    else:
        yield part


def _attachments(msg: EmailMessage, body_parts) -> list[MessageAttachment]:
    attachments = []
    for part in _leaf_parts(msg):
        if any(part is body for body in body_parts):
            continue
        try:
            filename = part.get_filename() or ""
        except Exception:
            filename = ""
        content_type = part.get_content_type()
        # Unnamed inline text parts are unused body alternatives. Any other part
        # is listed, so an unnamed program cannot slip past the attachment checks.
        if not filename and not part.is_attachment() and part.get_content_maintype() == "text":
            continue
        data = _payload(part)
        attachments.append(MessageAttachment(filename=filename, content_type=content_type,
                                             size_bytes=len(data), encrypted=_zip_is_encrypted(data)))
    return attachments


def _payload(part: EmailMessage) -> bytes:
    try:
        if part.is_multipart():  # an attached email
            return bytes(part.get_payload(0))
        return part.get_payload(decode=True) or b""
    except Exception:
        return b""


def _zip_is_encrypted(data: bytes) -> bool:
    """True when any zip entry has the encryption flag. Checked by content, not by
    name, so a zip renamed to .pdf is caught too."""
    if not data.startswith(b"PK"):
        return False
    try:
        return any(info.flag_bits & 0x1 for info in zipfile.ZipFile(io.BytesIO(data)).infolist())
    except Exception:  # not a readable zip after all
        return False


def _received_at(date: str | None) -> datetime:
    try:
        when = parsedate_to_datetime(date)
    except (TypeError, ValueError, OverflowError):  # missing or unreadable Date header
        return datetime.now(UTC)
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def _upload_id(message_id: str | None, recipients: list[str], raw: bytes) -> str:
    """Stable id, so the same email scanned twice is not stored twice."""
    basis = f"{message_id}|{','.join(sorted(recipients))}".encode() if message_id else raw
    return "eml-" + hashlib.sha256(basis).hexdigest()[:16]
