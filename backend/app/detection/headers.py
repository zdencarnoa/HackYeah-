"""Task 2: header checks.

Reads the receiving server's SPF, DKIM and DMARC verdicts from
Authentication-Results, and spots replies or error reports that go to a
different domain than From. Only reads headers; never looks anything up.
"""

import re
from email.utils import parseaddr

from app.detection.domains import domain_of, registrable
from app.schemas import DetectionResult, Message, Signal, SignalCategory

MECHANISMS = ("spf", "dkim", "dmarc")
RESULT_RE = re.compile(r"^(spf|dkim|dmarc)\s*=\s*([a-z]+)", re.IGNORECASE)
COMMENT_RE = re.compile(r"\([^()]*\)")
SYNONYMS = {"hardfail": "fail"}  # written by some older servers
# Failures in order of strength; the first one found sets severity and evidence.
# "pass" and "none" (nothing to check, or no policy) are not signals. Neither are
# "neutral" (the domain makes no claim), "policy", "temperror" or "permerror"
# (the check itself could not finish): they say nothing about the sender.
FAILURES = [
    ("dmarc", "fail", 2,
     "The domain {domain} could not confirm that it sent this email, so the sender address may be forged."),
    ("spf", "fail", 2,
     "The server that delivered this email is not allowed to send mail for {domain}, so the sender may be forged."),
    ("spf", "softfail", 1,
     "The server that delivered this email is probably not allowed to send mail for {domain}."),
    ("dkim", "fail", 1,
     "The digital seal on this email is broken, so it may have been changed on the way or not sent by {domain}."),
]
NO_AUTH_RESULTS = ("We could not check whether the sender's domain approved this email, "
                   "because it carries no authentication results.")


def check_headers(message: Message) -> DetectionResult:
    auth = read_auth_results(_values(message, "Authentication-Results"))
    signals = [s for s in (_auth_signal(auth, message), _reply_to_signal(message),
                           _return_path_signal(message)) if s is not None]
    unchecked = [] if auth else [NO_AUTH_RESULTS]
    if auth.get("dmarc", ("", ""))[0] == "none":
        domain = domain_of(message.sender) or "the sender's domain"
        unchecked.append(f"We could not confirm this email really comes from {domain}, "
                         "because that domain publishes no DMARC policy.")
    return DetectionResult(signals=signals, unchecked=unchecked)


def read_auth_results(values: list[str]) -> dict[str, tuple[str, str]]:
    """{mechanism: (result, server)} from every Authentication-Results header.

    Per mechanism the topmost header wins: the final receiving server adds it,
    while lower ones may have been forged by the sender. Comments in parentheses
    are dropped first, because they can quote sender-controlled text such as
    "; dmarc=pass".
    """
    results = {}
    for value in values:
        segments = _strip_comments(value).split(";")
        first = segments[0].strip()
        server = "" if not first or RESULT_RE.match(first) else first.split()[0]
        found = {}
        for segment in segments:
            match = RESULT_RE.match(segment.strip())
            if match:
                mechanism, result = match.group(1).lower(), match.group(2).lower()
                # Several DKIM signatures: one valid signature is enough.
                if mechanism not in found or result == "pass":
                    found[mechanism] = SYNONYMS.get(result, result)
        for mechanism, result in found.items():
            results.setdefault(mechanism, (result, server))
    return results


def _auth_signal(auth: dict[str, tuple[str, str]], message: Message) -> Signal | None:
    for mechanism, result, severity, evidence in FAILURES:
        if auth.get(mechanism, ("", ""))[0] == result:
            domain = domain_of(message.sender) or "the sender's domain"
            return Signal(id="header.auth", category=SignalCategory.AUTH_FAILURE, severity=severity,
                          evidence=evidence.format(domain=domain),
                          technical_detail=_auth_detail(auth), source="rule")
    return None


def _auth_detail(auth: dict[str, tuple[str, str]]) -> str:
    """"spf=softfail; dkim=none; dmarc=fail (from mx.lakeside-logistics.example)"."""
    found = [(mechanism, *auth[mechanism]) for mechanism in MECHANISMS if mechanism in auth]
    servers = {server for _, _, server in found}
    if len(servers) == 1:
        server = servers.pop()
        detail = "; ".join(f"{mechanism}={result}" for mechanism, result, _ in found)
        return f"{detail} (from {server})" if server else detail
    return "; ".join(f"{mechanism}={result} (from {server or 'an unnamed server'})"
                     for mechanism, result, server in found)


def _reply_to_signal(message: Message) -> Signal | None:
    sender_domain, reply_domain = domain_of(message.sender), domain_of(message.reply_to or "")
    if not _different(sender_domain, reply_domain):
        return None
    return Signal(id="header.reply_to", category=SignalCategory.REPLY_TO_MISMATCH, severity=2,
                  evidence=(f"If you reply, your answer goes to {message.reply_to}, "
                            f"not to {sender_domain}, where the email claims to come from."),
                  technical_detail=f"Reply-To: {message.reply_to}; From: {message.sender}",
                  source="rule")


def _return_path_signal(message: Message) -> Signal | None:
    values = _values(message, "Return-Path")
    return_path = parseaddr(values[0])[1].lower() if values else ""
    sender_domain, return_domain = domain_of(message.sender), domain_of(return_path)
    if not _different(sender_domain, return_domain):
        return None
    return Signal(id="header.return_path", category=SignalCategory.RETURN_PATH_MISMATCH, severity=1,
                  evidence=(f"Error reports for this email go to {return_domain} rather than {sender_domain}, "
                            "which newsletter services also do, so alone it means little."),
                  technical_detail=f"Return-Path: {return_path}; From: {message.sender}",
                  source="rule")


def _different(sender_domain: str, other_domain: str) -> bool:
    """Both domains known and on different registrable domains."""
    return bool(sender_domain and other_domain) and registrable(sender_domain) != registrable(other_domain)


def _strip_comments(value: str) -> str:
    """Drops (comments), including nested ones."""
    while True:
        stripped = COMMENT_RE.sub(" ", value)
        if stripped == value:
            return stripped
        value = stripped


def _values(message: Message, name: str) -> list[str]:
    return [value for key, value in message.headers if key.lower() == name.lower()]
