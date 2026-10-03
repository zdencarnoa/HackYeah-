"""Task 8: offline threat indicators.

Compares the sender, the links and the sending server with a local blocklist
snapshot (data/blocklist.json). Never looks anything up online: what cannot be
known offline, such as a domain's age, is an uncertainty for B, not a signal.
"""

import ipaddress
import json
import logging
import re
from functools import cache
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

from app.detection.domains import domain_of
from app.schemas import DetectionResult, Message, Signal, SignalCategory

log = logging.getLogger(__name__)

BLOCKLIST_PATH = Path(__file__).parent / "data" / "blocklist.json"
NO_BLOCKLIST = "We could not compare this email with our list of known bad senders and websites."
# "[203.0.113.14]" or "[IPv6:2001:db8::1]" in a Received header.
BRACKETED_IP_RE = re.compile(r"\[(?:IPv6:)?([0-9A-Fa-f:.]+)\]", re.IGNORECASE)


class Blocklist(NamedTuple):
    updated: str
    domains: frozenset[str]  # a listed domain also covers its subdomains
    urls: frozenset[str]  # normalized with _normalize_url
    senders: frozenset[str]  # lowercased addresses
    ips: frozenset[str]  # normalized by ipaddress


# (evidence, technical detail) for one blocklist hit.
Match = tuple[str, str]


def check_intel(message: Message) -> DetectionResult:
    try:
        blocklist = _read_blocklist(BLOCKLIST_PATH)
    except (OSError, ValueError, TypeError, AttributeError):  # missing or broken snapshot
        log.warning("blocklist %s could not be read", BLOCKLIST_PATH, exc_info=True)
        return DetectionResult(unchecked=[NO_BLOCKLIST])
    signals = []
    for rule_id, find in (("intel.sender", _sender_matches), ("intel.link", _link_matches),
                          ("intel.ip", _ip_matches)):
        matches = find(message, blocklist)
        if matches:  # one signal per rule: the first hit explains, every hit is in the detail
            details = "; ".join(dict.fromkeys(detail for _, detail in matches))
            signals.append(Signal(id=rule_id, category=SignalCategory.KNOWN_BAD, severity=3,
                                  evidence=matches[0][0], source="intel",
                                  technical_detail=f"{details}; blocklist updated {blocklist.updated}"))
    return DetectionResult(signals=signals)


def _sender_matches(message: Message, blocklist: Blocklist) -> list[Match]:
    matches = []
    for role, address in (("From", message.sender), ("Reply-To", message.reply_to or "")):
        if not address:
            continue
        if address in blocklist.senders:
            evidence = (f"The sender {address} is on our list of known phishing senders." if role == "From"
                        else f"Replies would go to {address}, which is on our list of known phishing senders.")
            matches.append((evidence, f"{role} {address} matches senders entry"))
        listed = _listed_domain(domain_of(address), blocklist.domains)
        if listed:
            where = "The email comes from" if role == "From" else "Replies would go to"
            matches.append((f"{where} {listed}, which is on our list of known phishing domains.",
                            f"{role} {address} matches domains entry '{listed}'"))
    return matches


def _link_matches(message: Message, blocklist: Blocklist) -> list[Match]:
    matches = []
    for link in message.urls:
        host = _host(link.url)
        url = _normalize_url(link.url)
        if url in blocklist.urls:
            matches.append((f"The link to {host or 'a website'} leads to a page on our list of known "
                            "phishing sites.", f"link {url} matches urls entry"))
        listed = _listed_domain(host, blocklist.domains)
        if listed:
            matches.append((f"The link leads to {listed}, which is on our list of known phishing sites.",
                            f"link host {host} matches domains entry '{listed}'"))
    return matches


def _ip_matches(message: Message, blocklist: Blocklist) -> list[Match]:
    matches = []
    for ip in _sending_ips(message):
        if ip in blocklist.ips:
            matches.append((f"This email was sent from a server ({ip}) that is on our list of known "
                            "phishing sources.", f"topmost Received IP {ip} matches ips entry"))
    for link in message.urls:
        ip = _ip(_host(link.url))
        if ip in blocklist.ips:
            matches.append((f"The link leads to a server ({ip}) that is on our list of known "
                            "phishing sources.", f"link host {ip} matches ips entry"))
    return matches


def _sending_ips(message: Message) -> list[str]:
    """IPs in the topmost Received header. Our own receiving server adds that one;
    lower ones are written by earlier servers and can be forged by the sender."""
    received = next((value for name, value in message.headers if name.lower() == "received"), "")
    return [ip for ip in map(_ip, BRACKETED_IP_RE.findall(received)) if ip]


def _listed_domain(host: str, domains: frozenset[str]) -> str | None:
    """The listed domain that host is or belongs to (login.bad.test -> bad.test)."""
    labels = host.lower().rstrip(".").split(".") if host else []
    for i in range(len(labels)):
        candidate = ".".join(labels[i:])
        if candidate in domains:
            return candidate
    return None


def _host(url: str) -> str:
    try:
        return urlsplit(url).hostname or ""
    except ValueError:  # an unreadable URL; task 5 judges links
        return ""


def _ip(text: str) -> str | None:
    try:
        return str(ipaddress.ip_address(text.strip()))
    except ValueError:
        return None


def _normalize_url(url: str) -> str:
    """Lowercase scheme and host, no trailing slash, so trivial variants still match."""
    url = url.strip()
    try:
        parts = urlsplit(url)
    except ValueError:
        return url.rstrip("/")
    return parts._replace(scheme=parts.scheme.lower(), netloc=parts.netloc.lower()).geturl().rstrip("/")


@cache
def _read_blocklist(path: Path) -> Blocklist:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Blocklist(
        updated=str(data.get("updated", "unknown")),
        domains=frozenset(d.strip().lower().rstrip(".") for d in data.get("domains", [])),
        urls=frozenset(_normalize_url(u) for u in data.get("urls", [])),
        senders=frozenset(s.strip().lower() for s in data.get("senders", [])),
        ips=frozenset(ip for ip in map(_ip, data.get("ips", [])) if ip),  # bad entries are skipped
    )
