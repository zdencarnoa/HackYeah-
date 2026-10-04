"""Campaign matching: pure Python, stdlib only (no DB, no pydantic).

Two suspicious messages belong together when enough independent traits agree.
Each trait is something an admin can verify by eye, so the result is explainable.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parseaddr
from itertools import combinations
from urllib.parse import urlsplit

WINDOW = timedelta(hours=24)  # delivery-time window
JOIN_SCORE = 2  # a pair joins a campaign at this score or higher

# Shared infrastructure says nothing about a common attacker: never match on these.
FREEMAIL = frozenset({
    "gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com", "proton.me",
    "protonmail.com", "wp.pl", "o2.pl", "onet.pl", "interia.pl", "gazeta.pl", "poczta.fm",
})
SHORTENERS = frozenset({"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "ow.ly", "cutt.ly", "rb.gy"})


@dataclass(frozen=True)
class MsgFeatures:
    id: str
    received_at: datetime  # timezone-aware
    sender: str  # full lowercase address
    sender_domain: str  # registered domain of the sender
    link_hosts: frozenset[str]
    link_urls: frozenset[str]
    shingles: frozenset[str]


def registered_domain(host: str) -> str:
    """Last two labels. Good enough for the demo; use the public-suffix list in production."""
    parts = host.lower().strip(".").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def _shingles(text: str, n: int = 3) -> frozenset[str]:
    text = re.sub(r"https?://\S+", " ", text.lower())  # link text differs per variant
    words = re.findall(r"\w+", text)
    if not words:
        return frozenset()
    return frozenset(" ".join(words[i:i + n]) for i in range(max(len(words) - n + 1, 1)))


def features(msg_id: str, sender: str, subject: str, body: str, urls: list[str],
             received_at: datetime, ignore_hosts: frozenset[str] = frozenset()) -> MsgFeatures:
    addr = (parseaddr(sender)[1] or sender).lower().strip()
    domain = registered_domain(addr.rsplit("@", 1)[-1]) if "@" in addr else ""
    hosts = set()
    for u in urls:
        host = (urlsplit(u).hostname or "").lower()
        if host and host not in ignore_hosts and registered_domain(host) not in SHORTENERS:
            hosts.add(host)
    return MsgFeatures(
        id=msg_id, received_at=received_at, sender=addr, sender_domain=domain,
        link_hosts=frozenset(hosts), link_urls=frozenset(u.split("#")[0] for u in urls),
        shingles=_shingles(f"{subject} {body}"),
    )


def text_similarity(a: MsgFeatures, b: MsgFeatures) -> float:
    if not a.shingles or not b.shingles:
        return 0.0
    return len(a.shingles & b.shingles) / len(a.shingles | b.shingles)


def pair_score(a: MsgFeatures, b: MsgFeatures, window: timedelta = WINDOW) -> tuple[int, list[str]]:
    if abs(a.received_at - b.received_at) > window:
        return 0, []
    score, reasons = 0, []
    if a.link_hosts & b.link_hosts:
        score += 2
        reasons.append("same link target")
    if a.sender_domain and a.sender_domain == b.sender_domain and a.sender_domain not in FREEMAIL:
        score += 2
        reasons.append("same sender domain")
    sim = text_similarity(a, b)
    if sim >= 0.8:
        score += 2
        reasons.append("near-identical wording")
    elif sim >= 0.5:
        score += 1
        reasons.append("similar wording")
    return score, reasons


def _duration(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s} seconds"
    if s < 3600:
        return f"{s // 60} minutes"
    return f"{s // 3600} hours"


def shared_traits(members: list[MsgFeatures]) -> list[str]:
    """Plain-language observations. They describe what the messages have in common
    and do not claim who sent them."""
    n = len(members)
    if n < 2:
        return []
    traits: list[str] = []

    common_urls = frozenset.intersection(*(m.link_urls for m in members))
    if common_urls:
        traits.append(f"Same link in all {n} messages: {sorted(common_urls)[0]}")
    else:
        host_counts = Counter(h for m in members for h in m.link_hosts)
        for host, count in host_counts.most_common(2):
            if count == n:
                traits.append(f"Same link target in all {n} messages: {host}")
            elif count * 2 >= n:
                traits.append(f"Link target {host} in {count} of {n} messages")

    addresses = {m.sender for m in members}
    domains = {m.sender_domain for m in members}
    if len(addresses) == 1:
        traits.append(f"Same sender address in all {n} messages: {next(iter(addresses))}")
    elif len(domains) == 1 and next(iter(domains)) not in FREEMAIL and next(iter(domains)):
        traits.append(
            f"Same sender domain in all {n} messages: {next(iter(domains))} "
            f"({len(addresses)} different addresses)")

    pairs = list(combinations(members[:30], 2))
    mean = sum(text_similarity(a, b) for a, b in pairs) / len(pairs)
    if mean >= 0.4:
        traits.append(f"Similar wording (about {round(mean * 100)}% shared phrasing)")

    span = (max(m.received_at for m in members) - min(m.received_at for m in members)).total_seconds()
    traits.append(f"All delivered within {_duration(span)}")
    return traits


def campaign_name(members: list[MsgFeatures]) -> str:
    domains = Counter(m.sender_domain for m in members if m.sender_domain)
    if domains:
        return f"Suspicious emails from {domains.most_common(1)[0][0]}"
    return "Suspicious email campaign"
