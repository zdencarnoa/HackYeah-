from email.message import EmailMessage


def make_eml(text="Hello", html=None, attachments=(), **headers) -> bytes:
    """A small .eml. Header keyword arguments use "_" for "-" (Reply_To); None drops a header."""
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
