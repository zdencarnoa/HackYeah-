"""Task 9: link rewriting. Every link in a delivered copy becomes {BASE_URL}/r/{token},
so a click is known the moment it happens, without anyone reporting it.

Order on delivery (D's mailbox): message_from_sim() -> detect() on the ORIGINAL
message -> rewrite_links() for each recipient's inbox copy. detect() on a rewritten
copy would only see localhost links.

Until C's database and incident intake exist, tokens live in memory and clicks are
logged. C swaps both in with configure(); D's reset calls clear_links().
"""

import logging
import os
import re
import secrets
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import NamedTuple
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from app.detection.ingest import TEXT_URL_RE, TRAILING_PUNCTUATION, web_url
from app.schemas import Message, SimEvent, SimEventType

log = logging.getLogger(__name__)

# Where the employee's browser reaches the backend.
BASE_URL = os.environ.get("DETECTION_BASE_URL", "http://localhost:8000").rstrip("/")
# Where demo pages live. D points this at the fake site; until then the
# placeholder in router.py answers.
DEMO_SITE_URL = os.environ.get("DEMO_SITE_URL", BASE_URL + "/demo").rstrip("/")
# A click is only ever forwarded to these reserved demo domains, never to a real site.
DEMO_TLDS = (".example", ".test")


class LinkRecord(NamedTuple):
    token: str
    original_url: str
    domain: str  # host of the original URL
    message_id: str
    employee_id: str


class InMemoryLinkStore:
    """Tokens for as long as the backend runs. C's link_tokens table replaces this
    with the same three methods, so tokens survive a restart mid-demo."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_token: dict[str, LinkRecord] = {}
        self._by_link: dict[tuple[str, str, str], str] = {}

    def issue(self, url: str, message_id: str, employee_id: str) -> LinkRecord:
        """The token for this link in this employee's copy; the same one every time."""
        key = (message_id, employee_id, url)
        with self._lock:
            if key in self._by_link:
                return self._by_token[self._by_link[key]]
            record = LinkRecord(token=secrets.token_urlsafe(16), original_url=url, domain=_host(url),
                                message_id=message_id, employee_id=employee_id)
            self._by_token[record.token] = record
            self._by_link[key] = record.token
            return record

    def get(self, token: str) -> LinkRecord | None:
        return self._by_token.get(token)

    def clear(self) -> None:
        with self._lock:
            self._by_token.clear()
            self._by_link.clear()


ClickHandler = Callable[[SimEvent], None]
# Clicks seen by the default handler, newest last.
recorded_clicks: list[SimEvent] = []


def log_click(event: SimEvent) -> None:
    """The default handler until C's incident intake exists: keep and log the event."""
    recorded_clicks.append(event)
    log.info("link clicked: employee %s, message %s, %s",
             event.employee_id, event.message_id, event.data.get("domain"))


_store = InMemoryLinkStore()
_on_click: ClickHandler = log_click


def configure(store=None, on_click: ClickHandler | None = None) -> None:
    """C plugs in the link_tokens table and the incident intake here."""
    global _store, _on_click
    if store is not None:
        _store = store
    if on_click is not None:
        _on_click = on_click


def clear_links() -> None:
    """For D's /api/sim/reset: forget every token and recorded click."""
    _store.clear()
    recorded_clicks.clear()


def rewrite_links(message: Message, employee_id: str) -> Message:
    """The copy of a message for one employee's inbox, with every web link replaced
    by a tracked one. Anchor text stays as it was. One token per message, employee
    and URL, so a click tells who clicked. Never run detect() on the result."""
    def tracked(url: str) -> str:
        return f"{BASE_URL}/r/{_store.issue(url, message.id, employee_id).token}"

    return message.model_copy(update={
        "body_text": _rewrite_text(message.body_text, tracked),
        "body_html": _rewrite_html(message.body_html, tracked) if message.body_html else message.body_html,
        "urls": [link.model_copy(update={"url": tracked(link.url)}) for link in message.urls],
    })


def follow(token: str) -> LinkRecord | None:
    """Records the click before anything else, so the admin sees it at once.
    None for an unknown token."""
    record = _store.get(token)
    if record is None:
        return None
    event = SimEvent(id=f"evt-{secrets.token_hex(8)}", type=SimEventType.LINK_CLICKED,
                     at=datetime.now(UTC), employee_id=record.employee_id, message_id=record.message_id,
                     data={"domain": record.domain, "url": record.original_url, "source": "automatic"})
    try:
        _on_click(event)
    except Exception:  # the employee still gets a page; the failure is in the log
        log.exception("recording the click on %s failed", token)
    return record


def demo_target(record: LinkRecord) -> str | None:
    """The demo page standing in for the original site, or None when the original
    is not a reserved demo domain: real websites are never opened."""
    if not record.domain.endswith(DEMO_TLDS):
        return None
    parts = urlsplit(record.original_url)
    query = f"?{parts.query}" if parts.query else ""
    return f"{DEMO_SITE_URL}/{record.domain}{parts.path or '/'}{query}"


def _rewrite_text(text: str, tracked: Callable[[str], str]) -> str:
    """Plain-text links, found exactly as ingestion finds them."""
    def replace(match: re.Match) -> str:
        found = match.group()
        url = web_url(found.rstrip(TRAILING_PUNCTUATION))
        return tracked(url) + found[len(found.rstrip(TRAILING_PUNCTUATION)):] if url else found

    return TEXT_URL_RE.sub(replace, text)


def _rewrite_html(html: str, tracked: Callable[[str], str]) -> str:
    """Only href values change; the visible text is left alone."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        url = web_url(a["href"])
        if url is not None:
            a["href"] = tracked(url)
    return str(soup)


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").rstrip(".")
    except ValueError:
        return ""
