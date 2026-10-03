"""Text normalization shared by training and inference (no heavy imports)."""
import re

URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.I)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
NUM_RE = re.compile(r"\d+")
WS_RE = re.compile(r"\s+")
MAX_CHARS = 5000  # the opening of an email carries the lure; long tails only slow training


def normalize(text: str) -> str:
    """Mask URLs, addresses and numbers so the model learns wording, not corpus-specific tokens."""
    text = text[:MAX_CHARS]
    text = URL_RE.sub(" URLTOKEN ", text)
    text = EMAIL_RE.sub(" EMAILTOKEN ", text)
    text = NUM_RE.sub("0", text)
    return WS_RE.sub(" ", text).strip().lower()


def email_text(subject: str, body: str) -> str:
    """The exact input format the models were trained on."""
    return f"{subject} \n {body}"
