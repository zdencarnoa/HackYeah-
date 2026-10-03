import io
import zipfile
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

import pytest

from app.detection import parse_eml
from app.schemas import Link

FIXTURES = Path(__file__).parent / "fixtures"
ATTACK_URL = "https://login.micr0soft-example.test/verify?session=7f3a00c9"


def make_eml(text="Hello", html=None, attachments=(), **headers) -> bytes:
    """A small .eml. Header keyword arguments use "_" for "-" (Reply_To)."""
    fields = {"From": "IT Helpdesk <helpdesk@lakeside-logistics.example>",
              "To": "alice.johnson@lakeside-logistics.example",
              "Subject": "Test", "Date": "Sat, 03 Oct 2026 09:00:00 +0000",
              "Message-ID": "<t1@lakeside-logistics.example>"}
    fields |= {name.replace("_", "-"): value for name, value in headers.items()}
    msg = EmailMessage()
    for name, value in fields.items():
        if value is not None:
            msg[name] = value
    if text is not None:
        msg.set_content(text)
    if html is not None:
        if text is None:
            msg.set_content(html, subtype="html")
        else:
            msg.add_alternative(html, subtype="html")
    for filename, content_type, data in attachments:
        maintype, subtype = content_type.split("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return msg.as_bytes()


def zip_bytes(encrypted: bool) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("report.txt", "quarterly numbers")
    data = bytearray(buf.getvalue())
    if encrypted:  # zipfile cannot write encrypted entries, so set the flag by hand
        data[6] |= 0x1
        data[data.find(b"PK\x01\x02") + 8] |= 0x1
    return bytes(data)


def test_outlook_export_is_parsed_completely():
    message = parse_eml((FIXTURES / "outlook_export.eml").read_bytes())

    assert message.sender == "security@micr0soft-example.test"
    assert message.sender_name == "Microsoft Security"
    assert message.reply_to == "help@micr0soft-support.test"
    assert message.recipients == ["alice.johnson@lakeside-logistics.example",
                                  "carol.williams@lakeside-logistics.example"]
    assert message.subject == "URGENT: Your account will be suspended – działaj teraz"
    assert message.received_at == datetime(2026, 10, 3, 9, 2, tzinfo=UTC)
    assert "zawieszone - pilne, żółć" in message.body_text  # iso-8859-2, quoted-printable
    assert "<b>suspended</b>" in message.body_html
    assert [name for name, _ in message.headers][:4] == [
        "Received", "Received", "Authentication-Results", "Authentication-Results"]
    assert message.headers[2] == ("Authentication-Results",
                                  "mx.lakeside-logistics.example; spf=pass smtp.mailfrom=micr0soft-example.test; "
                                  "dkim=none; dmarc=none header.from=micr0soft-example.test")
    # The text part's copy of the attack URL (split by a soft line break) is a
    # duplicate of the HTML links, which also know their anchor text.
    assert message.urls == [
        Link(url=ATTACK_URL, anchor_text="Verify your account now", found_in="html"),
        Link(url=ATTACK_URL, anchor_text="https://account.microsoft.example/verify", found_in="html"),
        Link(url="http://www.micr0soft-example.test/help", found_in="text"),
    ]
    assert [(a.filename, a.content_type, a.encrypted) for a in message.attachments] == [
        ("image001.png", "image/png", False),
        ("Security_Report.zip", "application/zip", True),
    ]


def test_links_in_plain_text():
    text = ("Go to https://a.example/x, or www.b.example/y. See (https://c.example/z) and\n"
            "<https://d.example/w>. Mail mailto:it@lakeside-logistics.example, call tel:+48123,\n"
            "or write to someone@www.e.example. Again: https://a.example/x!")
    urls = [link.url for link in parse_eml(make_eml(text)).urls]
    assert urls == ["https://a.example/x", "http://www.b.example/y",
                    "https://c.example/z", "https://d.example/w"]


def test_html_links_keep_anchor_text_and_skip_non_web_links():
    html = f"""<p><a href="{ATTACK_URL}">https://account.microsoft.example/verify</a>
        <a href=" https://login.micr0soft-example.test/verify?ses
sion=7f3a00c9 ">Verify   now</a>
        <a href="{ATTACK_URL}">Verify now</a>
        <a href="https://cdn.example/x"><img src="logo.png" alt="Microsoft logo"></a>
        <a href="mailto:it@lakeside-logistics.example">Mail us</a> <a href="tel:+48123">Call</a>
        <a href="#top">Top</a> <a href="/relative/path">Relative</a> <a>No href</a></p>"""
    message = parse_eml(make_eml(text=f"Verify now: {ATTACK_URL}", html=html))
    assert message.urls == [
        Link(url=ATTACK_URL, anchor_text="https://account.microsoft.example/verify", found_in="html"),
        Link(url=ATTACK_URL, anchor_text="Verify now", found_in="html"),
        Link(url="https://cdn.example/x", anchor_text="Microsoft logo", found_in="html"),
    ]


def test_html_only_email_gets_its_visible_text_as_body_text():
    html = ("<html><head><title>T</title><style>p {color: red}</style></head><body>"
            "<script>var x = 'hidden';</script><p>Your account will be <b>suspended</b> today.</p>"
            "<div>Second&nbsp;block</div><table><tr><td>A</td><td>B</td></tr></table></body></html>")
    message = parse_eml(make_eml(text=None, html=html))
    assert message.body_text == "Your account will be suspended today.\nSecond block\nA\nB"
    assert message.body_html == html + "\n"


def test_unknown_or_broken_charset_does_not_crash():
    raw = (b"From: a@example.test\r\nTo: b@example.test\r\nSubject: Hi\r\n"
           b"Content-Type: text/plain; charset=\"x-no-such-charset\"\r\n\r\n"
           b"Za\xc5\xbc\xc3\xb3\xc5\x82\xc4\x87 \xff\xfe link https://x.example/a\r\n")
    message = parse_eml(raw)
    assert "Zażółć" in message.body_text
    assert [link.url for link in message.urls] == ["https://x.example/a"]


@pytest.mark.parametrize(("date", "expected"), [
    ("Sat, 03 Oct 2026 11:00:00 +0200", datetime(2026, 10, 3, 9, 0, tzinfo=UTC)),
    ("Sat, 03 Oct 2026 09:00:00 -0000", datetime(2026, 10, 3, 9, 0, tzinfo=UTC)),
    ("not a date", None),
    (None, None),
])
def test_received_at_comes_from_the_date_header_or_falls_back_to_now(date, expected):
    received_at = parse_eml(make_eml(Date=date)).received_at
    assert received_at.tzinfo is not None
    if expected is None:
        assert abs(datetime.now(UTC) - received_at) < timedelta(minutes=1)
    else:
        assert received_at == expected


@pytest.mark.parametrize(("from_header", "name", "address"), [
    ("Microsoft Security <Security@Micr0soft-Example.test>", "Microsoft Security",
     "security@micr0soft-example.test"),
    ("security@micr0soft-example.test", "", "security@micr0soft-example.test"),
    ('"Clark, James (CEO)" <james.clark.ceo@freemail.test>', "Clark, James (CEO)",
     "james.clark.ceo@freemail.test"),
    ("=?utf-8?b?WmVzcMOzxYIgSVQ=?= <it@lakeside-it-support.test>", "Zespół IT",
     "it@lakeside-it-support.test"),
])
def test_sender_display_name_and_address(from_header, name, address):
    message = parse_eml(make_eml(From=from_header))
    assert (message.sender_name, message.sender) == (name, address)


def test_missing_parts_are_left_empty():
    message = parse_eml(b"From: someone@example.test\r\n\r\n")
    assert message.subject == ""
    assert message.recipients == []
    assert message.reply_to is None
    assert message.body_text == ""
    assert message.body_html is None
    assert message.urls == []
    assert message.attachments == []


def test_id_is_stable_and_differs_per_recipient():
    raw = make_eml()
    assert parse_eml(raw).id == parse_eml(raw).id
    assert parse_eml(raw).id != parse_eml(make_eml(To="carol.williams@lakeside-logistics.example")).id
    no_message_id = make_eml(Message_ID=None)
    assert parse_eml(no_message_id).id == parse_eml(no_message_id).id
    assert parse_eml(raw).id.startswith("eml-")


def test_attachment_metadata_and_encrypted_zip():
    message = parse_eml(make_eml(attachments=[
        ("INV-20431.pdf", "application/pdf", b"%PDF-1.4 fake"),
        ("photos.zip", "application/zip", zip_bytes(encrypted=False)),
        ("invoice.zip", "application/zip", zip_bytes(encrypted=True)),
        ("statement.pdf", "application/pdf", zip_bytes(encrypted=True)),  # a zip in disguise
    ]))
    assert [(a.filename, a.content_type, a.size_bytes, a.encrypted) for a in message.attachments] == [
        ("INV-20431.pdf", "application/pdf", 13, False),
        ("photos.zip", "application/zip", len(zip_bytes(False)), False),
        ("invoice.zip", "application/zip", len(zip_bytes(True)), True),
        ("statement.pdf", "application/pdf", len(zip_bytes(True)), True),
    ]


def test_attached_email_is_one_attachment_and_is_not_opened():
    inner = EmailMessage()
    inner["From"] = "x@example.test"
    inner.set_content("inner")
    inner.add_attachment(b"MZ", maintype="application", subtype="octet-stream", filename="tool.exe")
    outer = EmailMessage()
    outer["From"] = "y@example.test"
    outer.set_content("See the forwarded message.")
    outer.add_attachment(inner)
    attachments = parse_eml(outer.as_bytes()).attachments
    assert [a.content_type for a in attachments] == ["message/rfc822"]
    assert attachments[0].size_bytes > 0


@pytest.mark.parametrize("content_type", [
    b'multipart/mixed',                   # no boundary at all
    b'multipart/mixed; boundary="zz"',    # boundary never used
])
def test_malformed_multipart_body_is_still_scanned(content_type):
    raw = (b"From: a@example.test\r\nSubject: s\r\nContent-Type: " + content_type +
           b"\r\n\r\nVerify now: https://login.micr0soft-example.test/verify\r\n")
    message = parse_eml(raw)
    assert "Verify now" in message.body_text
    assert [link.url for link in message.urls] == ["https://login.micr0soft-example.test/verify"]


def test_unnamed_non_text_part_is_listed_as_attachment():
    raw = (b"From: a@example.test\r\nSubject: s\r\nContent-Type: application/x-msdownload\r\n"
           b"Content-Transfer-Encoding: base64\r\n\r\nTVo=\r\n")
    attachments = parse_eml(raw).attachments
    assert [(a.filename, a.content_type, a.size_bytes) for a in attachments] == [
        ("", "application/x-msdownload", 2)]


@pytest.mark.parametrize("raw", [
    b"",
    b"hello world\n",
    b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj",
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
], ids=["empty", "text", "pdf", "png"])
def test_files_that_are_not_email_are_rejected(raw):
    with pytest.raises(ValueError):
        parse_eml(raw)
