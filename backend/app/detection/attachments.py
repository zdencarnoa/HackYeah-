"""Task 7: attachment rules.

Judged only by name, type and the zip encryption flag that ingestion read from
the zip's table of contents. Attachments are never opened, unpacked or run.
"""

import re
from typing import NamedTuple

from app.schemas import DetectionResult, Message, MessageAttachment, Signal, SignalCategory

RIGHT_TO_LEFT_OVERRIDE = "\u202e"  # shows the rest of a name reversed
POP_DIRECTIONAL = "\u202c"  # ends the override
# Direction controls and other invisible control characters, removed before checks.
HIDDEN_CHARS = dict.fromkeys([*range(0x00, 0x20), *range(0x7f, 0xa0), 0x061c, 0x200e, 0x200f,
                              *range(0x202a, 0x202f), *range(0x2066, 0x206a)])
# Windows ignores trailing dots and spaces, so "invoice.exe. " is an .exe.
TRAILING_RE = re.compile(r"[\s.]+$")
# Attacker-controlled names quoted in evidence stay short. The end is kept,
# because that is where the real extension is.
MAX_QUOTE = 60
MAX_DETAIL = 120

# Extensions that run code when opened, by what they are.
RISKY_EXTENSIONS = {
    **dict.fromkeys(["exe", "scr", "com", "pif", "msi", "cpl", "jar", "msc"], "program"),
    **dict.fromkeys(["js", "jse", "vbs", "vbe", "bat", "cmd", "ps1", "hta", "wsf", "wsh"], "script"),
    **dict.fromkeys(["iso", "img", "vhd", "vhdx"], "disk_image"),
    "lnk": "shortcut",
    "reg": "settings",
}
KINDS = {  # kind: (what it is, what opening it does)
    "program": ("a program", "Opening it would run it."),
    "script": ("a script, a small program", "Opening it would run it."),
    "disk_image": ("a disk image", "Opening it can unpack hidden programs."),
    "shortcut": ("a shortcut", "Opening it can run a hidden command."),
    "settings": ("a Windows settings file", "Opening it would change your computer's settings."),
}
# Harmless-looking extensions put in front of the real one, or shown instead of it.
DECOYS = {
    "pdf": "a PDF",
    **dict.fromkeys(["doc", "docx", "odt", "rtf"], "a Word document"),
    **dict.fromkeys(["xls", "xlsx", "ods", "csv"], "a spreadsheet"),
    **dict.fromkeys(["ppt", "pptx", "odp"], "a presentation"),
    "txt": "a text file",
    **dict.fromkeys(["jpg", "jpeg", "png", "gif", "bmp"], "a picture"),
    **dict.fromkeys(["mp3", "mp4", "wav", "avi", "mov"], "a media file"),
    **dict.fromkeys(["zip", "rar", "7z"], "an archive"),
}
# New Office formats that may hold macros, plus the old formats, which always can.
MACRO_EXTENSIONS = {"docm", "dotm", "xlsm", "xltm", "xlam", "pptm", "potm", "ppsm",
                    "doc", "dot", "xls", "xlt", "ppt", "pot", "pps"}
HTML_EXTENSIONS = {"html", "htm", "shtml", "xhtml"}
HTML_TYPES = {"text/html", "application/xhtml+xml"}
ARCHIVE_EXTENSIONS = {"zip", "7z", "rar"}
ARCHIVE_TYPES = {"application/zip", "application/x-zip", "application/x-zip-compressed",
                 "application/x-7z-compressed", "application/x-rar", "application/x-rar-compressed",
                 "application/vnd.rar"}
PROGRAM_TYPES = {"application/x-msdownload", "application/x-dosexec", "application/x-msdos-program",
                 "application/x-executable", "application/vnd.microsoft.portable-executable",
                 "application/x-msi", "application/x-ms-installer", "application/hta",
                 "application/x-sh", "application/x-bat", "application/java-archive",
                 "application/x-ms-shortcut", "application/javascript", "application/x-javascript",
                 "text/javascript", "text/vbscript"}
# A password handed over in the email: "password: 1234", "the password is x1",
# "password for the archive: 1234", "hasło do pliku: 1234".
PASSWORD_RE = re.compile(r"\b(?:password|passcode|pwd|has[łl]o)(?:\s+(?:for|to|do)(?:\s+\w+){1,2})?"
                         r"\s*(?::|=|\bis\b|\bto\b)\s*\S+", re.IGNORECASE)
SEVERITIES = {  # rule id: severity, in reporting order
    "attachment.double_extension": 3,
    "attachment.risky_extension": 3,
    "attachment.type_mismatch": 3,
    "attachment.macro_office": 2,
    "attachment.html": 2,
    "attachment.encrypted_archive": 2,
}


class Finding(NamedTuple):
    rule: str
    evidence: str
    detail: str


def check_attachments(message: Message) -> DetectionResult:
    password = PASSWORD_RE.search(f"{message.subject}\n{message.body_text}")
    by_rule: dict[str, list[Finding]] = {}
    for attachment in message.attachments:
        finding = _finding(attachment, password.group() if password else None)
        if finding is not None:
            by_rule.setdefault(finding.rule, []).append(finding)

    signals = []
    for rule, severity in SEVERITIES.items():
        findings = by_rule.get(rule)
        if not findings:
            continue
        evidence, detail = findings[0].evidence, findings[0].detail
        if len(findings) > 1:  # one signal per rule: the first file is named, the rest listed
            more = len(findings) - 1
            evidence += f" The email has {more} more file{'s' if more > 1 else ''} like it."
            detail += "; also " + "; ".join(f.detail for f in findings[1:5])
        signals.append(Signal(id=rule, category=SignalCategory.RISKY_ATTACHMENT, severity=severity,
                              evidence=evidence, technical_detail=detail, source="rule"))
    return DetectionResult(signals=signals)


def _finding(attachment: MessageAttachment, password: str | None) -> Finding | None:
    """The strongest rule one attachment breaks, or None. One finding per file,
    so 'invoice.pdf.exe' is reported as a disguise, not twice."""
    original, content_type = attachment.filename, attachment.content_type
    name = TRAILING_RE.sub("", _clean(original).strip().lower())
    real = _extension(name)
    shown = _quote(_displayed(original))
    label = f"'{shown}'" if shown else "An attachment without a name"
    detail = f"filename {_short(repr(original), MAX_DETAIL)}, type {content_type}"

    if real in RISKY_EXTENSIONS:
        kind, consequence = KINDS[RISKY_EXTENSIONS[real]]
        if RIGHT_TO_LEFT_OVERRIDE in original:
            return Finding("attachment.double_extension",
                           f"The file shows as '{shown}', but a hidden character reverses its name: "
                           f"it is actually {kind}. {consequence}",
                           f"right-to-left override (U+202E); real extension .{real}; {detail}")
        decoy = _extension(TRAILING_RE.sub("", name.rpartition(".")[0]))
        if decoy in DECOYS:
            return Finding("attachment.double_extension",
                           f"{label} pretends to be {DECOYS[decoy]} but is actually {kind}. {consequence}",
                           f"double extension .{decoy} then .{real}; {detail}")
        if real == "com":  # "www.microsoft.com" reads as a website, not a program
            return Finding("attachment.risky_extension",
                           f"{label} looks like a web address but is a program file. Opening it would run it.",
                           f"risky extension .com; {detail}")
        return Finding("attachment.risky_extension", f"{label} is {kind}. {consequence}",
                       f"risky extension .{real}; {detail}")

    if content_type in PROGRAM_TYPES:  # the name hides that it is a program
        if not shown:
            evidence = "An attachment without a name is marked as a program. Opening it could run it."
        elif real in DECOYS:
            evidence = (f"{label} looks like {DECOYS[real]}, but the email marks it as a program. "
                        "Opening it could run it.")
        else:
            evidence = f"{label} does not look like a program, but the email marks it as one. Opening it could run it."
        return Finding("attachment.type_mismatch", evidence,
                       f"program content type, extension {'.' + real if real else 'none'}; {detail}")

    if real in MACRO_EXTENSIONS:
        return Finding("attachment.macro_office",
                       f"{label} is an Office file that can contain macros: small programs that run "
                       "if you click 'Enable content'.",
                       f"macro-capable Office extension .{real}; {detail}")

    if real in HTML_EXTENSIONS or content_type in HTML_TYPES:
        return Finding("attachment.html",
                       f"{label} opens a web page from your computer, a common way to show a fake "
                       "login or payment form.",
                       f"HTML attachment; {detail}")

    if attachment.encrypted:
        what = "a" if real in ARCHIVE_EXTENSIONS else "really a"
        return Finding("attachment.encrypted_archive",
                       f"{label} is {what} password-protected archive, a common way to hide malware "
                       "from security scanners.",
                       f"zip entries carry the encryption flag; {detail}")
    if password and (real in ARCHIVE_EXTENSIONS or content_type in ARCHIVE_TYPES):
        return Finding("attachment.encrypted_archive",
                       f"{label} is an archive and the email gives its password, a common way to hide "
                       "malware from security scanners.",
                       f"archive with a password in the email ({_short(password, MAX_QUOTE)!r}); {detail}")
    return None


def _clean(text: str) -> str:
    return text.translate(HIDDEN_CHARS)


def _displayed(filename: str) -> str:
    """Roughly what a mail client shows: text after a right-to-left override
    appears reversed, so "invoice\u202efdp.exe" reads as "invoiceexe.pdf"."""
    before, override, after = filename.partition(RIGHT_TO_LEFT_OVERRIDE)
    if not override:
        return _clean(filename)
    reversed_part, _, rest = after.partition(POP_DIRECTIONAL)
    return _clean(before) + _clean(reversed_part)[::-1] + _clean(rest)


def _extension(name: str) -> str:
    stem, dot, extension = name.rpartition(".")
    return extension.strip() if dot else ""


def _quote(text: str) -> str:
    return _short(" ".join(text.split()), MAX_QUOTE)


def _short(text: str, limit: int) -> str:
    """Cut from the middle, keeping the end where the real extension is."""
    if len(text) <= limit:
        return text
    tail = limit // 3
    return text[:limit - tail - 1].rstrip() + "…" + text[-tail:].lstrip()
