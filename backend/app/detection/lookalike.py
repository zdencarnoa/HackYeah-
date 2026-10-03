"""Task 4: lookalike domains. Does the sender's domain or a link's domain imitate
a name people trust, such as micr0soft-example.test for Microsoft?

The part of a domain that is actually bought (its registrable label) is compared
with the names in data/brands.json after undoing look-alike characters, allowing
one typo on longer names. Offline: punycode is decoded locally, nothing is looked up.
"""

import ipaddress
import json
from functools import cache
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

from app.detection.domains import domain_of, registrable
from app.schemas import DetectionResult, Message, Signal, SignalCategory

DATA_DIR = Path(__file__).parent / "data"
# Characters that pass for Latin letters: digits and symbols, then Cyrillic and
# Greek letters that look identical in most fonts.
HOMOGLYPHS = {"0": "o", "1": "l", "3": "e", "5": "s", "@": "a",
              "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "і": "i",
              "ѕ": "s", "ј": "j", "ԁ": "d", "һ": "h", "ο": "o", "α": "a"}
# Letter pairs that read as one letter at a glance.
MULTI = {"rn": "m", "vv": "w", "cl": "d"}
# One typo is only allowed on names this long: "dhx" must not match "dhl".
MIN_TYPO_LENGTH = 5
# Names this long are also found inside a longer label ("micr0softsupport").
MIN_EMBEDDED_LENGTH = 6


class Target(NamedTuple):
    key: str  # brand key in brands.json
    name: str  # brand name, "Microsoft"
    written: str  # the name as written in brands.json, "lakeside-logistics"
    norm: str  # normalized, without hyphens
    subs: tuple[tuple[str, str], ...]  # look-alikes inside the real name itself ("office365")


class Lookalike(NamedTuple):
    host: str
    target: Target
    trick: str  # plain-language trick; "" when the name is simply reused
    detail: str  # technical: what matched and how


def check_lookalike(message: Message) -> DetectionResult:
    signals = []
    sender_domain = domain_of(message.sender)
    sender = find_lookalike(sender_domain) if sender_domain else None
    if sender:
        signals.append(_sender_signal(sender))
    links = []
    for link in message.urls:
        match = find_lookalike(_host(link.url))
        if match and match.host not in {m.host for m in links}:
            links.append(match)
    if links:
        signals.append(_link_signal(links))
    return DetectionResult(signals=signals)


def find_lookalike(host: str) -> Lookalike | None:
    """The trusted name this host imitates, or None. A brand's real domains, their
    subdomains, free-mail providers and IP addresses are never lookalikes."""
    host = (host or "").strip().lower().rstrip(".")
    if not host or _is_ip(host):
        return None
    reg = registrable(host)
    label = _decode_punycode(reg.split(".")[0])
    if not label or reg in _real_domains() or registrable(_decode_punycode(reg)) in _real_domains():
        return None
    tokens = [token for token in label.split("-") if token]
    candidates = [_squash(label)] + (tokens if len(tokens) > 1 else [])
    plain = None
    for position, candidate in enumerate(candidates):
        norm, subs = normalize(candidate)
        for target in _targets():
            compared = _compare(candidate, norm, subs, target, whole_label=position == 0)
            if compared is None:
                continue
            trick, kind = compared
            detail = (f"{host}: registrable {reg}; '{candidate}' normalizes to '{norm}'; "
                      f"matches {target.key} name '{target.written}' ({kind})")
            if label != reg.split(".")[0]:
                detail += f"; punycode {reg.split('.')[0]} decodes to '{label}'"
            found = Lookalike(host=host, target=target, trick=trick, detail=detail)
            if trick:  # a disguised name is stronger evidence than a reused one
                return found
            plain = plain or found
    return plain


def normalize(label: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    """(label with look-alikes undone, substitutions made, in order of first use)."""
    label = label.lower()
    out, subs, i = [], [], 0
    while i < len(label):
        pair = label[i:i + 2]
        if pair in MULTI:
            fake, real, i = pair, MULTI[pair], i + 2
        else:
            fake, i = label[i], i + 1
            real = HOMOGLYPHS.get(fake, fake)
        out.append(real)
        if fake != real and (fake, real) not in subs:
            subs.append((fake, real))
    return "".join(out), tuple(subs)


def edit_distance(a: str, b: str) -> int:
    """Changes needed to turn a into b: insert, delete, replace, or swap two
    neighbouring letters (optimal string alignment)."""
    if abs(len(a) - len(b)) > 1 and min(len(a), len(b)) > 0:
        return abs(len(a) - len(b))  # more than one edit apart; exact value not needed
    before, previous = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        current = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            current[j] = min(previous[j] + 1, current[j - 1] + 1,
                             previous[j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                current[j] = min(current[j], before[j - 2] + 1)
        before, previous = previous, current
    return previous[len(b)]


def _compare(candidate: str, norm: str, subs, target: Target, whole_label: bool) -> tuple[str, str] | None:
    """(trick in plain words, kind of match in technical words), or None when
    there is no match. The trick is "" when the name is reused as is."""
    tricks = [sub for sub in subs if sub not in target.subs]
    if norm == target.norm:
        return _describe_subs(tricks), _kind("same name", tricks)
    if len(target.norm) >= MIN_TYPO_LENGTH and edit_distance(norm, target.norm) == 1:
        position_char = _edit_char(candidate, norm, target.norm)
        tricks = [sub for sub in tricks if sub[0] != position_char]
        trick = " and ".join(filter(None, [_describe_subs(tricks), _describe_edit(candidate, norm, target.norm)]))
        return trick, _kind("edit distance 1", tricks)
    if whole_label and len(target.norm) >= MIN_EMBEDDED_LENGTH and target.norm in norm:
        # "microsoft-0nline" reuses the real name; only a disguised name is a trick.
        if _squash(target.written) in candidate:
            return "", "name embedded in a longer domain"
        return _describe_subs(tricks), _kind("name embedded in a longer domain", tricks)
    return None


def _kind(kind: str, tricks) -> str:
    return f"{kind}, homoglyphs {', '.join(f'{fake}→{real}' for fake, real in tricks)}" if tricks else kind


def _describe_subs(subs) -> str:
    parts = []
    for fake, real in subs[:2]:
        if len(fake) == 2:
            parts.append(f"the letters '{fake}' stand in for the letter '{real}'")
        elif fake.isdigit():
            parts.append(f"the letter '{real}' was replaced by the digit '{fake}'")
        elif fake.isascii():
            parts.append(f"the letter '{real}' was replaced by '{fake}'")
        else:
            parts.append(f"the letter '{real}' was replaced by a look-alike letter from another alphabet")
    return " and ".join(parts)


def _describe_edit(candidate: str, a: str, b: str) -> str:
    """One edit between normalized candidate a and target b, in everyday words."""
    i = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
    if len(a) == len(b):
        if i + 1 < len(a) and a[i] == b[i + 1] and a[i + 1] == b[i]:
            return f"the letters '{b[i]}{b[i + 1]}' were swapped"
        shown = candidate[i] if len(candidate) == len(a) else a[i]
        by = f"the digit '{shown}'" if shown.isdigit() else f"'{shown}'"
        return f"the letter '{b[i]}' was replaced by {by}"
    if len(a) > len(b):
        return f"an extra '{a[i]}' was added to '{b}'"
    return f"the letter '{b[i]}' was left out of '{b}'"


def _edit_char(candidate: str, a: str, b: str) -> str | None:
    """The candidate's own character where a same-length edit happened, if any."""
    if len(a) != len(b) or len(candidate) != len(a):
        return None
    return next((candidate[i] for i in range(len(a)) if a[i] != b[i]), None)


def _sender_signal(match: Lookalike) -> Signal:
    domain, target = match.host, match.target
    if match.trick:
        evidence = f"The sender's domain {domain} imitates {_who(target)}: {match.trick}."
    elif target.key == "company":
        evidence = f"The sender's domain {domain} uses our company's name, but it is not our company's domain."
    else:
        evidence = f"The sender's domain {domain} uses the name {target.name}, but it is not a {target.name} address."
    return Signal(id="lookalike.sender", category=SignalCategory.LOOKALIKE_DOMAIN, severity=3,
                  evidence=evidence, technical_detail=match.detail, source="rule")


def _link_signal(matches: list[Lookalike]) -> Signal:
    match = matches[0]
    host, target = match.host, match.target
    if match.trick:
        evidence = f"The link leads to {host}, an imitation of {_who(target)}: {match.trick}."
    elif target.key == "company":
        evidence = f"The link leads to {host}, which uses our company's name but is not our company's website."
    else:
        evidence = f"The link leads to {host}, which uses the name {target.name} but is not a {target.name} website."
    return Signal(id="lookalike.link", category=SignalCategory.SUSPICIOUS_URL, severity=3,
                  evidence=evidence, technical_detail=" | ".join(m.detail for m in matches[:3]),
                  source="url")


def _who(target: Target) -> str:
    return "our company's domain" if target.key == "company" else target.name


def _host(url: str) -> str:
    try:
        return urlsplit(url).hostname or ""
    except ValueError:  # an unreadable URL; task 5 judges links
        return ""


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def _decode_punycode(text: str) -> str:
    """Decodes "xn--" labels, so a Cyrillic "microsoft" is compared letter by letter."""
    labels = []
    for label in text.split("."):
        try:
            labels.append(label.encode("ascii").decode("idna") if label.startswith("xn--") else label)
        except (UnicodeError, ValueError):
            labels.append(label)
    return ".".join(labels)


def _squash(text: str) -> str:
    return "".join(text.lower().replace("-", " ").split())


@cache
def _brands() -> tuple[dict, ...]:
    return tuple(json.loads((DATA_DIR / "brands.json").read_text(encoding="utf-8")))


@cache
def _freemail() -> frozenset[str]:
    return frozenset(json.loads((DATA_DIR / "freemail.json").read_text(encoding="utf-8")))


@cache
def _real_domains() -> frozenset[str]:
    """Every registrable domain a brand really uses, plus free-mail providers."""
    return frozenset(registrable(d) for brand in _brands() for d in brand["domains"]) | _freemail()


@cache
def _targets() -> tuple[Target, ...]:
    """Names worth imitating: a brand's domain labels and key, but only when they
    are also one of its keywords. That skips generic labels such as "office" and
    placeholder keys such as "company". For a hyphenated name the distinctive first
    part counts too ("lakeside" in lakeside-logistics), never the generic rest."""
    targets = []
    for brand in _brands():
        keywords = {_squash(keyword) for keyword in brand["keywords"]}
        names = [brand["key"]] if _squash(brand["key"]) in keywords else []
        for domain in brand["domains"]:
            reg = registrable(domain)
            label = reg.split(".")[0]
            if reg in _freemail() or _squash(label) not in keywords:
                continue
            names.append(label)
            first = label.split("-")[0]
            if "-" in label and len(first) >= MIN_EMBEDDED_LENGTH:
                names.append(first)
        for written in dict.fromkeys(names):
            norm, subs = normalize(_squash(written))
            targets.append(Target(key=brand["key"], name=brand["name"], written=written, norm=norm, subs=subs))
    return tuple(targets)
