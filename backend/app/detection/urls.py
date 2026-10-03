"""Task 5: URL checks. Where do the links really lead?

Only the original URLs are judged, never rewritten /r/{token} links. Nothing is
fetched or expanded: a short link stays a short link. The lookalike-host rule
lives in lookalike.py (Task 4).
"""

import ipaddress
import json
import re
from functools import cache
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

from app.detection.domains import registrable
from app.schemas import DetectionResult, Link, Message, Signal, SignalCategory

DATA_DIR = Path(__file__).parent / "data"
# Attacker-controlled text quoted in evidence stays short (it reaches B's LLM).
MAX_QUOTE = 60
# Endings that make "word.word" in link text a web address. File extensions
# (pdf, docx, zip, exe, ...) are deliberately absent, so "INV-20431.pdf" is no domain.
SHOWN_TLDS = {"com", "net", "org", "info", "biz", "io", "co", "app", "dev", "eu", "pl", "de", "uk",
              "fr", "nl", "es", "us", "ru", "cn", "me", "ly", "gl", "be", "ch", "at", "cz", "se",
              "no", "dk", "fi", "ie", "pt", "ca", "au", "jp", "gov", "edu", "online", "site", "xyz",
              "top", "live", "shop", "cloud", "tech", "store", "example", "test"}
SCHEME_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
# A host written without a scheme. Not part of an email address or a longer word.
BARE_HOST_RE = re.compile(r"(?<![\w@.-])((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+([a-z]{2,24}))(?![\w-])")
# Path words of sign-in and "confirm your details" pages. Not inside a longer
# word on the left, so "/insecure-news" is not "secure".
LOGIN_PATH_RE = re.compile(r"(?<![a-z])(log-?in|sign-?in|sign-?on|verif(?:y|ication)|account|"
                           r"password|passwd|secure|update|confirm)")
SUBDOMAIN_DEPTH = 3  # "a.b.c.evil.example": three levels in front of the real site


class Url(NamedTuple):
    link: Link
    host: str  # lowercased, without port or user info
    path: str
    userinfo: str  # text before "@" in the address, "" when there is none


def check_urls(message: Message) -> DetectionResult:
    urls = [url for url in map(_parse, message.urls) if url is not None]
    signals = []
    for rule_id, severity, rule in RULES:
        hits = [hit for hit in (_apply(rule, url) for url in urls) if hit is not None]
        if not hits:
            continue
        details = list(dict.fromkeys(detail for _, detail in hits))[:3]
        signals.append(Signal(id=rule_id, category=SignalCategory.SUSPICIOUS_URL, severity=severity,
                              evidence=hits[0][0], technical_detail="; ".join(details), source="url"))
    return DetectionResult(signals=signals)


def _text_mismatch(url: Url) -> tuple[str, str] | None:
    """The link text shows one website, but the link leads to another."""
    shown = _shown_hosts(url.link.anchor_text or "")
    real = registrable(url.host)
    if not shown or real in {registrable(host) for host in shown}:
        return None
    return (f"The link shows {_quote(shown[0])} but actually leads to {_quote(url.host)}.",
            f"anchor text shows {_quote(shown[0])} (registrable {registrable(shown[0])}); "
            f"href host {_quote(url.host)} (registrable {real})")


def _at_sign(url: Url) -> tuple[str, str] | None:
    """https://microsoft.com@evil.example: the browser ignores everything before "@"."""
    if not url.userinfo:
        return None
    fake = url.userinfo.partition(":")[0]
    if "." in fake:
        evidence = f"The link looks like it goes to {_quote(fake)} but really goes to {_quote(url.host)}."
    else:
        evidence = f"The link hides extra text in front of the real address, which is {_quote(url.host)}."
    return evidence, f"user info '{_quote(url.userinfo)}' before @; real host {_quote(url.host)}"


def _ip_host(url: Url) -> tuple[str, str] | None:
    ip = _ip_address(url.host)
    if ip is None:
        return None
    return (f"The link goes to a bare number address ({ip}) instead of a named website.",
            f"IP-literal host {_quote(url.host)}" + (f" = {ip}" if str(ip) != url.host else ""))


def _brand_subdomain(url: Url) -> tuple[str, str] | None:
    """microsoft.com.account-check.example starts with a brand's address but is not the brand's site."""
    real = registrable(url.host)
    if _ip_address(url.host) is not None or not url.host.endswith("." + real):
        return None
    subdomain = url.host[:-len(real) - 1]
    for domain, brand in _brand_domains().items():
        if f".{domain}." in f".{subdomain}." and real not in _brand_registrables(brand):
            return (f"The address starts with '{domain}', but the real website is {_quote(real)}.",
                    f"{brand} domain {domain} in the subdomain of {_quote(url.host)}")
    return None


def _punycode(url: Url) -> tuple[str, str] | None:
    """Letters from another alphabet that look like Latin ones (Cyrillic "і" in "mіcrosoft")."""
    labels = url.host.split(".")
    if not url.host.isascii():
        decoded, encoded = url.host, ".".join(_to_punycode(label) for label in labels)
    elif any(label.startswith("xn--") for label in labels):
        decoded, encoded = ".".join(_from_punycode(label) for label in labels), url.host
    else:
        return None
    return (f"The web address {_quote(decoded)} uses letters from another alphabet that look like normal "
            f"ones, so it may not be the site it seems to be.",
            f"punycode host {_quote(encoded)} decodes to {_quote(decoded)}")


def _deep_subdomain(url: Url) -> tuple[str, str] | None:
    real = registrable(url.host)
    if _ip_address(url.host) is not None or not url.host.endswith("." + real):
        return None
    depth = len(url.host[:-len(real) - 1].split("."))
    if depth < SUBDOMAIN_DEPTH:
        return None
    return (f"The web address {_quote(url.host)} is unusually long and nested, which can hide the real "
            f"site, {_quote(real)}.",
            f"{depth} subdomain levels in {_quote(url.host)}")


def _shortener(url: Url) -> tuple[str, str] | None:
    if url.host not in _shorteners() and registrable(url.host) not in _shorteners():
        return None
    return (f"The link uses a shortening service ({_quote(url.host)}), which hides where it really goes.",
            f"URL shortener {_quote(url.host)}; not expanded (no live lookups)")


def _login_path(url: Url) -> tuple[str, str] | None:
    match = LOGIN_PATH_RE.search(url.path.lower())
    if match is None:
        return None
    return (f"The link leads to a sign-in or verification page on {_quote(url.host)}.",
            f"login-path keyword '{match.group(1)}' in {_quote(url.host + url.path)}")


# Strongest first. At most one signal per rule; the first link that matches sets the evidence.
RULES = [
    ("url.text_mismatch", 3, _text_mismatch),
    ("url.at_sign", 3, _at_sign),
    ("url.ip_host", 2, _ip_host),
    ("url.brand_subdomain", 2, _brand_subdomain),
    ("url.punycode", 2, _punycode),
    ("url.deep_subdomain", 1, _deep_subdomain),
    ("url.shortener", 1, _shortener),
    ("url.login_path", 1, _login_path),
]


def _parse(link: Link) -> Url | None:
    """None for a URL that cannot be read; such links are skipped, never fatal."""
    try:
        parts = urlsplit(link.url)
        host = (parts.hostname or "").rstrip(".")
    except ValueError:  # e.g. "http://[::1" (unclosed IPv6 bracket)
        return None
    if not host:
        return None
    userinfo = parts.netloc.rpartition("@")[0]
    return Url(link=link, host=host, path=parts.path, userinfo=userinfo)


def _apply(rule, url: Url) -> tuple[str, str] | None:
    try:
        return rule(url)
    except Exception:  # one odd URL must not cost the other links their checks
        return None


def _shown_hosts(text: str) -> list[str]:
    """Web addresses that the link text shows to the reader, in order."""
    text = text.lower()
    hosts = []
    for match in SCHEME_URL_RE.finditer(text):
        try:
            host = urlsplit(match.group().rstrip(".,;:!?)")).hostname
        except ValueError:
            continue
        if host:
            hosts.append(host.rstrip("."))
    for match in BARE_HOST_RE.finditer(SCHEME_URL_RE.sub(" ", text)):
        host, tld = match.group(1), match.group(2)
        if tld in SHOWN_TLDS or host.startswith("www."):
            hosts.append(host)
    return hosts


def _ip_address(host: str):
    """The IP address a browser would use, also for a bare number such as 3221225994."""
    try:
        return ipaddress.ip_address(int(host) if host.isdigit() else host)
    except ValueError:
        return None


def _from_punycode(label: str) -> str:
    if not label.startswith("xn--"):
        return label
    try:
        return label[4:].encode("ascii").decode("punycode")
    except UnicodeError:
        return label


def _to_punycode(label: str) -> str:
    if label.isascii():
        return label
    try:
        return "xn--" + label.encode("punycode").decode("ascii")
    except UnicodeError:
        return label


def _quote(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= MAX_QUOTE else text[:MAX_QUOTE - 1].rstrip() + "…"


@cache
def _brand_domains() -> dict[str, str]:
    """{brand domain: brand key}, longest domains first."""
    brands = json.loads((DATA_DIR / "brands.json").read_text(encoding="utf-8"))
    pairs = [(domain.lower(), brand["key"]) for brand in brands for domain in brand["domains"]]
    return dict(sorted(pairs, key=lambda pair: (-len(pair[0]), pair[0])))


@cache
def _brand_registrables(key: str) -> frozenset[str]:
    return frozenset(registrable(domain) for domain, brand in _brand_domains().items() if brand == key)


@cache
def _shorteners() -> frozenset[str]:
    return frozenset(json.loads((DATA_DIR / "shorteners.json").read_text(encoding="utf-8")))
