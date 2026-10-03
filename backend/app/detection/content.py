"""Task 6: content rules. Keyword and pattern rules on the subject and the body:
pressure to act fast, requests for sign-in details, changed bank details, gift
cards and sign-in codes.

Evidence quotes the sentence that matched, kept to one short sentence: the quote
is attacker-written text, and it reaches B's LLM.
"""

import json
import logging
import re
from functools import cache
from pathlib import Path
from typing import NamedTuple

from app.detection.ingest import visible_text
from app.schemas import DetectionResult, Message, Signal, SignalCategory

log = logging.getLogger(__name__)

KEYWORDS_FILE = Path(__file__).parent / "data" / "keywords.json"
MAX_QUOTE = 120
MAX_PHRASE = 40  # matched phrases listed in technical_detail
MAX_SCAN = 100_000  # characters per part; a huge body cannot slow the scan down
# (key in keywords.json, category, severity, evidence with the quoted sentence)
RULES = [
    ("urgency", SignalCategory.URGENCY, 2, 'The email pushes you to act fast: "{quote}"'),
    ("credential_request", SignalCategory.CREDENTIAL_REQUEST, 2,
     'The email asks you to sign in or confirm your account details: "{quote}"'),
    ("payment_change", SignalCategory.PAYMENT_CHANGE, 3,
     'The email says the bank account for a payment has changed: "{quote}"'),
    ("gift_card", SignalCategory.GIFT_CARD, 3,
     'The email asks for gift cards, which scammers like because they cannot be traced: "{quote}"'),
    ("mfa_code_request", SignalCategory.MFA_CODE_REQUEST, 3,
     'The email asks you to share a sign-in code or approve sign-in prompts: "{quote}"'),
]
# Where a sentence ends. In plain text a single line break is usually just
# wrapping, so it only ends a sentence after a colon ("Verify your account now:").
TEXT_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+|(?<=:)[ \t]*\n|\n[ \t]*\n")
# In text taken from HTML every line is its own block.
HTML_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+|\n")


class Rule(NamedTuple):
    key: str
    category: SignalCategory
    severity: int
    evidence: str
    pattern: re.Pattern


class Part(NamedTuple):
    name: str  # "subject", "body text", "HTML body"
    text: str
    sentence_end: re.Pattern


def check_content(message: Message) -> DetectionResult:
    parts = _parts(message)
    signals = []
    for rule in _rules():
        found = [(part, match) for part in parts for match in rule.pattern.finditer(part.text)]
        if not found:
            continue
        part, first = found[0]  # one signal per category, quoting the first match
        quote = _quote(_sentence_at(part, first.start()), first.group())
        phrases = list(dict.fromkeys(_short(match.group()) for _, match in found))
        where = list(dict.fromkeys(part.name for part, _ in found))
        signals.append(Signal(
            id=f"content.{rule.key}", category=rule.category, severity=rule.severity,
            evidence=rule.evidence.format(quote=quote), source="rule",
            technical_detail=(f"{rule.key} phrases: {', '.join(repr(p) for p in phrases[:5])}; "
                              f"found in {', '.join(where)}")))
    return DetectionResult(signals=signals)


def _parts(message: Message) -> list[Part]:
    """Subject, text body and the visible text of the HTML body, which can say
    something different from the text body."""
    parts = [Part("subject", message.subject[:MAX_SCAN], TEXT_SENTENCE_END_RE),
             Part("body text", message.body_text[:MAX_SCAN], TEXT_SENTENCE_END_RE)]
    if message.body_html:
        try:
            parts.append(Part("HTML body", visible_text(message.body_html[:MAX_SCAN]), HTML_SENTENCE_END_RE))
        except Exception:  # unreadable HTML: the text parts are still checked
            log.warning("could not read the HTML body of %s", message.id)
    return parts


def _sentence_at(part: Part, position: int) -> str:
    """The sentence of the part that contains the position."""
    start, end = 0, len(part.text)
    for boundary in part.sentence_end.finditer(part.text):
        if boundary.end() <= position:
            start = boundary.end()
        else:
            end = boundary.start()
            break
    return part.text[start:end]


def _quote(sentence: str, matched: str) -> str:
    """The sentence on one line, cut around the match to at most MAX_QUOTE characters."""
    sentence = " ".join(sentence.split()).rstrip(":;,")
    if len(sentence) <= MAX_QUOTE:
        return sentence
    at = max(sentence.lower().find(_short(matched, limit=len(sentence))), 0)
    room = MAX_QUOTE - 2  # leaves space for an ellipsis on both sides
    start = min(max(at - 30, 0), len(sentence) - room)
    window = sentence[start:start + room]
    if start > 0 and not sentence[start - 1].isspace():  # do not start mid-word
        window = window.partition(" ")[2] or window
    if start + room < len(sentence) and not sentence[start + room].isspace():  # nor end mid-word
        window = window.rpartition(" ")[0] or window
    return ("…" if start > 0 else "") + window.strip() + ("…" if start + room < len(sentence) else "")


def _short(text: str, limit: int = MAX_PHRASE) -> str:
    text = " ".join(text.lower().split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _phrase_re(phrase: str) -> str:
    """Whole words; spaces and hyphens inside the phrase match any whitespace or hyphen."""
    words = [re.escape(word) for word in re.split(r"[\s-]+", phrase.strip()) if word]
    return r"(?<!\w)" + r"[\s-]*".join(words) + r"(?!\w)"


@cache
def _rules() -> tuple[Rule, ...]:
    data = json.loads(KEYWORDS_FILE.read_text(encoding="utf-8"))
    languages = [entries for name, entries in data.items() if not name.startswith("_")]
    rules = []
    for key, category, severity, evidence in RULES:
        phrases = sorted({p for lang in languages for p in lang.get(key, {}).get("phrases", [])},
                         key=lambda p: (-len(p), p))  # the longest phrase wins at one position
        patterns = [p for lang in languages for p in lang.get(key, {}).get("patterns", [])]
        alternatives = [_phrase_re(p) for p in phrases] + patterns
        if alternatives:
            rules.append(Rule(key, category, severity, evidence,
                              re.compile("|".join(f"(?:{a})" for a in alternatives), re.IGNORECASE)))
    return tuple(rules)
