import io
import zipfile

import pytest

from app.detection import detect, message_from_sim, parse_eml
from app.detection.attachments import check_attachments
from app.schemas import SignalCategory
from app.simulation.seed import load_emails
from tests.detection.helpers import make_eml

EMAILS = load_emails()
BY_ID = {sim.id: sim for sim in EMAILS}
LEGIT = [sim for sim in EMAILS if sim.scenario.label == "legitimate"]


def zip_bytes(encrypted: bool) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("report.txt", "quarterly numbers")
    data = bytearray(buf.getvalue())
    if encrypted:  # zipfile cannot write encrypted entries, so set the flag by hand
        data[6] |= 0x1
        data[data.find(b"PK\x01\x02") + 8] |= 0x1
    return bytes(data)


def signals_for(*attachments, text="Please see the attached file."):
    """{rule id: signal} for an email with these (filename, content type, bytes) attachments."""
    message = parse_eml(make_eml(text=text, attachments=attachments))
    return {signal.id: signal for signal in check_attachments(message).signals}


def only(signals: dict, rule: str):
    assert list(signals) == [rule], {s.id: s.evidence for s in signals.values()}
    signal = signals[rule]
    assert signal.category == SignalCategory.RISKY_ATTACHMENT and signal.source == "rule"
    return signal


@pytest.mark.parametrize(("filename", "says"), [
    ("setup.exe", "is a program. Opening it would run it."),
    ("Update.JS", "is a script, a small program."),
    ("run.bat", "is a script"),
    ("screensaver.scr", "is a program"),
    ("installer.msi", "is a program"),
    ("invoice.iso", "is a disk image. Opening it can unpack hidden programs."),
    ("Report.lnk", "is a shortcut. Opening it can run a hidden command."),
    ("fix.reg", "is a Windows settings file"),
    ("invoice.exe. ", "is a program"),  # Windows ignores trailing dots and spaces
    ("www.microsoft.com", "looks like a web address but is a program file"),
])
def test_risky_extension(filename, says):
    signal = only(signals_for((filename, "application/octet-stream", b"MZ")), "attachment.risky_extension")
    assert signal.severity == 3
    assert says in signal.evidence


@pytest.mark.parametrize(("filename", "pretends"), [
    ("invoice.pdf.exe", "a PDF"),
    ("invoice.pdf      .exe", "a PDF"),
    ("scan.jpg.....scr", "a picture"),
    ("contract.docx.js", "a Word document"),
    ("faktura żółta.xlsx.bat", "a spreadsheet"),
])
def test_double_extension(filename, pretends):
    signal = only(signals_for((filename, "application/octet-stream", b"MZ")), "attachment.double_extension")
    assert signal.severity == 3
    assert f"pretends to be {pretends} but is actually" in signal.evidence


def test_double_extension_evidence_matches_the_guide():
    signal = only(signals_for(("invoice.pdf.exe", "application/octet-stream", b"MZ")),
                  "attachment.double_extension")
    assert signal.evidence == "'invoice.pdf.exe' pretends to be a PDF but is actually a program. Opening it would run it."
    assert ".pdf then .exe" in signal.technical_detail


def test_right_to_left_override_disguise():
    signal = only(signals_for(("invoice\u202efdp.exe", "application/octet-stream", b"MZ")),
                  "attachment.double_extension")
    assert "'invoiceexe.pdf'" in signal.evidence  # what the employee saw
    assert "is actually a program" in signal.evidence
    assert "\u202e" not in signal.evidence  # the trick itself never reaches the UI
    assert "\\u202e" in signal.technical_detail


@pytest.mark.parametrize("filename", ["budget.xlsm", "letter.docm", "deck.pptm", "addin.xlam",
                                      "template.dotm", "report.doc", "old.xls", "slides.ppt"])
def test_macro_office(filename):
    signal = only(signals_for((filename, "application/octet-stream", b"x")), "attachment.macro_office")
    assert signal.severity == 2
    assert "can contain macros" in signal.evidence


@pytest.mark.parametrize(("filename", "content_type"), [
    ("INV-20431_new_bank_details.html", "text/html"),
    ("page.HTM", "application/octet-stream"),
    ("form.xhtml", "application/xhtml+xml"),
    ("statement", "text/html"),
])
def test_html_attachment(filename, content_type):
    signal = only(signals_for((filename, content_type, b"<html></html>")), "attachment.html")
    assert signal.severity == 2
    assert "opens a web page from your computer" in signal.evidence


def test_encrypted_zip():
    signal = only(signals_for(("invoice.zip", "application/zip", zip_bytes(encrypted=True))),
                  "attachment.encrypted_archive")
    assert signal.severity == 2
    assert signal.evidence.startswith("'invoice.zip' is a password-protected archive")


def test_encrypted_zip_disguised_as_pdf():
    signal = only(signals_for(("statement.pdf", "application/pdf", zip_bytes(encrypted=True))),
                  "attachment.encrypted_archive")
    assert "is really a password-protected archive" in signal.evidence


@pytest.mark.parametrize(("filename", "content_type", "text"), [
    ("invoice.zip", "application/zip", "Invoice attached. Password: 1234"),
    ("docs.7z", "application/octet-stream", "The password is x1y2."),
    ("scan.rar", "application/octet-stream", "password for the archive: 9876"),
    ("faktura.zip", "application/zip", "W załączniku faktura. Hasło: 2024"),
    ("archive", "application/x-zip-compressed", "pwd=4321"),
])
def test_archive_with_password_in_the_email(filename, content_type, text):
    signals = signals_for((filename, content_type, zip_bytes(encrypted=False)), text=text)
    signal = only(signals, "attachment.encrypted_archive")
    assert "the email gives its password" in signal.evidence


@pytest.mark.parametrize(("filename", "says"), [
    ("statement.pdf", "looks like a PDF, but the email marks it as a program"),
    ("data.bin", "does not look like a program, but the email marks it as one"),
    (None, "An attachment without a name is marked as a program"),
])
def test_type_mismatch(filename, says):
    signal = only(signals_for((filename, "application/x-msdownload", b"MZ")), "attachment.type_mismatch")
    assert signal.severity == 3
    assert says in signal.evidence


@pytest.mark.parametrize(("filename", "content_type", "data"), [
    ("report.pdf", "application/pdf", b"%PDF-1.4"),
    ("invite.ics", "text/calendar", b"BEGIN:VCALENDAR"),
    ("photo.jpg", "image/jpeg", b"\xff\xd8\xff"),
    ("notes.txt", "text/plain", b"notes"),
    ("contract.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"PK"),
    ("photos.zip", "application/zip", zip_bytes(encrypted=False)),
    ("backup.tar.gz", "application/gzip", b"\x1f\x8b"),
    ("example.com.pdf", "application/pdf", b"%PDF-1.4"),
    (None, "image/png", b"\x89PNG"),
])
def test_harmless_attachments_give_no_signal(filename, content_type, data):
    assert signals_for((filename, content_type, data)) == {}


def test_zip_without_a_password_and_password_without_an_archive_are_fine():
    assert signals_for(("photos.zip", "application/zip", zip_bytes(False)),
                       text="Your password was changed yesterday.") == {}
    assert signals_for(("report.pdf", "application/pdf", b"%PDF"), text="Password: 1234") == {}


def test_web_address_in_the_body_is_not_an_attachment():
    message = parse_eml(make_eml(text="Download it from example.com or run setup.exe from the portal."))
    assert check_attachments(message).signals == []


def test_several_files_breaking_one_rule_give_one_signal():
    signals = signals_for(("a.pdf.exe", "application/octet-stream", b"MZ"),
                          ("b.doc.scr", "application/octet-stream", b"MZ"),
                          ("c.jpg.js", "application/octet-stream", b"MZ"),
                          ("budget.xlsm", "application/octet-stream", b"x"))
    assert list(signals) == ["attachment.double_extension", "attachment.macro_office"]
    double = signals["attachment.double_extension"]
    assert double.evidence.startswith("'a.pdf.exe' pretends to be a PDF")
    assert double.evidence.endswith("The email has 2 more files like it.")
    assert "'b.doc.scr'" in double.technical_detail and "'c.jpg.js'" in double.technical_detail


@pytest.mark.parametrize("filename", [".", "...", "\u202e", "\u202e\u202c", ".exe", "a" * 500 + ".pdf.exe",
                                      "файл.exe", "x\x00y.exe", "noextension"])
def test_odd_names_never_crash_and_quotes_stay_short(filename):
    message = parse_eml(make_eml(attachments=[(filename, "application/octet-stream", b"MZ")]))
    for signal in check_attachments(message).signals:
        quoted = signal.evidence.split("'")[1] if "'" in signal.evidence else ""
        assert len(quoted) <= 60
        assert "\u202e" not in signal.evidence and "\x00" not in signal.evidence


def test_long_names_keep_the_real_extension_visible():
    signal = signals_for(("a" * 500 + ".pdf.exe", "application/octet-stream", b"MZ"))["attachment.double_extension"]
    assert ".pdf.exe'" in signal.evidence


def test_invoice_fraud_html_attachment():
    signals = {s.id: s for s in check_attachments(message_from_sim(BY_ID["phi-01"])).signals}
    assert signals["attachment.html"].severity == 2
    assert "INV-20431_new_bank_details.html" in signals["attachment.html"].evidence


@pytest.mark.parametrize("sim", LEGIT, ids=lambda sim: sim.id)
def test_legitimate_demo_mail_has_no_attachment_signal(sim):
    signals = check_attachments(message_from_sim(sim)).signals
    assert signals == [], [s.evidence for s in signals]


def test_detect_includes_attachment_signals():
    message = parse_eml(make_eml(attachments=[("invoice.pdf.exe", "application/octet-stream", b"MZ")]))
    assert "attachment.double_extension" in {s.id for s in detect(message).signals}
