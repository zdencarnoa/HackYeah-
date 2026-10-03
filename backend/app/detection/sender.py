"""Task 3: sender checks. Who does the email claim to be, and does the sender
address back that up?

Only facts about the claim are reported. B's risk fusion decides what they mean.
"""

import json
import re
from functools import cache
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

from app.detection.domains import domain_of, registrable
from app.schemas import DetectionResult, Employee, Message, Signal, SignalCategory
from app.simulation.seed import load_org

DATA_DIR = Path(__file__).parent / "data"
# The last lines of the body, where people sign. "Sent from my phone" is skipped.
SIGNATURE_LINES = 2
DEVICE_LINE_RE = re.compile(r"^sent from my\b", re.IGNORECASE)
# Attacker-controlled text quoted in evidence stays short (it reaches B's LLM).
MAX_QUOTE = 60
# Role words that claim a position inside a company. Acronyms must be in capitals,
# so the pronoun "it" in "I need it today" is not read as "IT".
ROLE_ACRONYMS_RE = re.compile(r"\b(?:CEO|CFO|COO|CTO|CIO|IT|HR)\b")
ROLE_PHRASES = ["chief executive", "chief financial", "chief operating", "managing director",
                "director", "president", "head of", "finance department", "finance team",
                "accounts payable", "accounting", "human resources", "helpdesk", "help desk",
                "administrator"]


class Brand(NamedTuple):
    key: str
    name: str
    pattern: re.Pattern  # any of the brand's keywords, as whole words
    domains: frozenset[str]  # registrable domains the brand really sends from


def check_sender(message: Message) -> DetectionResult:
    domain = domain_of(message.sender)
    if not domain:
        return DetectionResult(unchecked=[
            "We could not check who sent this email, because it has no sender address."])

    brand_name = _brand_name(message, domain)
    colleague = _colleague_name(message, domain)
    # Rule 2 is for neutral display names, and rule 3 would only repeat a claim
    # that rule 1 or rule 4 already reports.
    brand_content = None if brand_name else _brand_content(message, domain)
    freemail_role = None if brand_name or colleague else _freemail_role(message, domain)
    signals = [s for s in (brand_name, brand_content, freemail_role, colleague) if s is not None]
    return DetectionResult(signals=signals)


def _brand_name(message: Message, domain: str) -> Signal | None:
    """The display name claims a brand, but the address is not one of the brand's."""
    named = [brand for brand in _brands() if brand.pattern.search(message.sender_name)]
    # A real brand address may name other brands too ("Microsoft Teams for Lakeside Logistics").
    if not named or any(_is_official(domain, brand) for brand in named):
        return None
    brand = named[0]
    name = _quote(message.sender_name)
    if _is_freemail(domain):
        evidence = (f"The sender calls itself '{name}', but writes from a personal {domain} "
                    f"address, not an official {brand.name} one.")
    else:
        evidence = (f"The sender calls itself '{name}', but the email comes from {domain}, "
                    f"which is not a {brand.name} address.")
    keyword = brand.pattern.search(message.sender_name).group()
    return Signal(id="sender.brand_name", category=SignalCategory.BRAND_IMPERSONATION, severity=3,
                  evidence=evidence, source="rule",
                  technical_detail=f"display name matches {brand.key} keyword '{keyword}'; "
                                   f"{_domain_detail(domain)}; {brand.key} domains: "
                                   f"{', '.join(sorted(brand.domains))}")


def _brand_content(message: Message, domain: str) -> Signal | None:
    """The subject or signature names a brand, but the links lead elsewhere.

    Kept narrow because legitimate mail mentions brands all the time: only the
    subject and the signature count (not the body in between), mail from our own
    organization is skipped, and the email must link somewhere outside the brand.
    """
    if any(brand.pattern.search(message.sender_name) for brand in _brands()):
        return None
    if registrable(domain) == _org_domain():  # internal mail about a brand is not impersonation
        return None
    signature = "\n".join(_signature(message.body_text))
    hosts = [_link_domain(link.url) for link in message.urls]
    for brand in _brands():
        in_signature = brand.pattern.search(signature)
        in_subject = brand.pattern.search(message.subject)
        if not (in_signature or in_subject) or _is_official(domain, brand):
            continue
        outside = sorted({host for host in hosts if host and host not in brand.domains})
        if not outside:
            continue
        where = ", ".join(outside[:3])
        if in_signature:
            severity, keyword = 2, in_signature.group()
            evidence = (f"The email is signed as {brand.name}, but its links lead to {where}, "
                        f"not to a {brand.name} website.")
        else:  # a subject that only mentions a brand is a weaker claim
            severity, keyword = 1, in_subject.group()
            evidence = (f"The subject mentions {brand.name}, but the email's links lead to {where}, "
                        f"not to a {brand.name} website.")
        return Signal(id="sender.brand_content", category=SignalCategory.BRAND_IMPERSONATION,
                      severity=severity, evidence=evidence, source="rule",
                      technical_detail=f"{brand.key} keyword '{keyword}' in "
                                       f"{'signature' if in_signature else 'subject'}; "
                                       f"link domains outside {brand.key}: {', '.join(outside)}")
    return None


def _freemail_role(message: Message, domain: str) -> Signal | None:
    """A personal free-mail address that claims a role or name inside a company."""
    if not _is_freemail(domain):
        return None
    claim = _role_claim(message.sender_name)
    if claim:
        evidence = (f"The sender calls themselves '{_quote(message.sender_name)}' but writes from "
                    f"a personal {domain} address, not a company one.")
        where = "display name"
    else:
        line, claim = next(((line, _role_claim(line)) for line in _signature(message.body_text)
                            if _role_claim(line)), ("", None))
        if not claim:
            return None
        evidence = (f"The email is signed '{_quote(line)}' but comes from a personal {domain} "
                    f"address, not a company one.")
        where = "signature"
    return Signal(id="sender.freemail_role", category=SignalCategory.FREEMAIL_IMPERSONATION,
                  severity=2, evidence=evidence, source="rule",
                  technical_detail=f"free-mail sender domain {registrable(domain)}; "
                                   f"role claim '{claim}' in {where}")


def _colleague_name(message: Message, domain: str) -> Signal | None:
    """The display name is a colleague's full name, but the address is not ours."""
    if registrable(domain) == _org_domain():
        return None
    employee = next((e for pattern, e in _colleagues() if pattern.search(message.sender_name)), None)
    if employee is None:
        return None
    if _is_freemail(domain):
        severity = 3
        evidence = (f"The sender uses the name of your colleague {employee.name} ({employee.title}) "
                    f"but writes from a personal {domain} address.")
    else:
        severity = 2
        evidence = (f"The sender uses the name of your colleague {employee.name} ({employee.title}) "
                    f"but writes from {domain}, outside the company.")
    return Signal(id="sender.colleague_name", category=SignalCategory.COLLEAGUE_IMPERSONATION,
                  severity=severity, evidence=evidence, source="rule",
                  technical_detail=f"display name matches employee {employee.id} ({employee.email}); "
                                   f"{_domain_detail(domain)}; organization domain {_org_domain()}")


def _role_claim(text: str) -> str | None:
    """The first role word or company name in the text, or None."""
    for pattern in (ROLE_ACRONYMS_RE, _role_phrases_re(), _company().pattern):
        match = pattern.search(text)
        if match:
            return match.group()
    return None


def _signature(body: str) -> list[str]:
    lines = [line.strip() for line in body.splitlines()]
    lines = [line for line in lines if line and not DEVICE_LINE_RE.match(line)]
    return lines[-SIGNATURE_LINES:]


def _link_domain(url: str) -> str:
    try:
        return registrable(urlsplit(url).hostname or "")
    except ValueError:  # an unreadable URL; task 5 judges links
        return ""


def _is_freemail(domain: str) -> bool:
    return registrable(domain) in _freemail()


def _is_official(domain: str, brand: Brand) -> bool:
    """Free-mail never counts: anyone can open "Microsoft Security <x@outlook.com>"."""
    return registrable(domain) in brand.domains and not _is_freemail(domain)


def _domain_detail(domain: str) -> str:
    kind = "free-mail" if _is_freemail(domain) else "not free-mail"
    return f"sender domain {domain} (registrable {registrable(domain)}, {kind})"


def _quote(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= MAX_QUOTE else text[:MAX_QUOTE - 1].rstrip() + "…"


def _words_re(phrases: list[str], flags=re.IGNORECASE) -> re.Pattern:
    """Whole-word match of any phrase; spaces inside a phrase match any whitespace."""
    alternatives = "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in sorted(phrases, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", flags)


@cache
def _brands() -> tuple[Brand, ...]:
    data = json.loads((DATA_DIR / "brands.json").read_text(encoding="utf-8"))
    return tuple(Brand(key=b["key"], name=b["name"], pattern=_words_re(b["keywords"]),
                       domains=frozenset(registrable(d) for d in b["domains"])) for b in data)


@cache
def _freemail() -> frozenset[str]:
    return frozenset(json.loads((DATA_DIR / "freemail.json").read_text(encoding="utf-8")))


@cache
def _company() -> Brand:
    return next(brand for brand in _brands() if brand.key == "company")


@cache
def _role_phrases_re() -> re.Pattern:
    return _words_re(ROLE_PHRASES)


@cache
def _org_domain() -> str:
    return registrable(load_org().domain)


@cache
def _colleagues() -> tuple[tuple[re.Pattern, Employee], ...]:
    """Each employee's full name, as "First Last" or "Last, First"."""
    found = []
    for employee in load_org().employees:
        first, _, last = employee.name.partition(" ")
        if not last:
            continue
        name_re = rf"(?:{re.escape(first)}\s+{re.escape(last)}|{re.escape(last)},?\s+{re.escape(first)})"
        found.append((re.compile(rf"(?<!\w){name_re}(?!\w)", re.IGNORECASE), employee))
    return tuple(found)
