"""detect(): runs every check on a Message and collects the signals.

Facts, not verdicts: B's risk fusion turns the signals into a risk level.
"""

import logging

from app.detection.attachments import check_attachments
from app.detection.content import check_content
from app.detection.headers import check_headers
from app.detection.intel import check_intel
from app.detection.lookalike import check_lookalike
from app.detection.sender import check_sender
from app.detection.urls import check_urls
from app.schemas import DetectionResult, Message

log = logging.getLogger(__name__)

# (check, what it looks at), in plain language for the unchecked list.
CHECKS = [
    (check_headers, "the sender's authentication results and reply addresses"),
    (check_sender, "who the sender claims to be"),
    (check_lookalike, "whether the sender or the links imitate a known name"),
    (check_urls, "where the links really lead"),
    (check_content, "the wording of the email"),
    (check_attachments, "the attachments"),
    (check_intel, "our list of known bad senders and websites"),
]


def detect(message: Message) -> DetectionResult:
    """Deterministic: the same message always gives the same signals in the same order."""
    signals, unchecked = {}, []
    for check, what in CHECKS:
        try:
            result = check(message)
        except Exception:  # one broken rule must never break the demo
            log.exception("check %s failed", check.__name__)
            unchecked.append(f"We could not check {what} because of an internal error.")
            continue
        for signal in result.signals:  # one signal per rule; the strongest wins
            if signal.id not in signals or signal.severity > signals[signal.id].severity:
                signals[signal.id] = signal
        unchecked += result.unchecked
    ordered = sorted(signals.values(), key=lambda s: (-s.severity, s.category, s.id))
    return DetectionResult(signals=ordered, unchecked=unchecked)
