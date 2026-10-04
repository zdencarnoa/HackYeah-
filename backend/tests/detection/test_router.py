from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.detection import message_from_sim, parse_eml, render_eml, rewrite, rewrite_links
from app.detection.router import MAX_UPLOAD_BYTES, router
from app.simulation.seed import load_emails
from tests.detection.helpers import make_eml

BY_ID = {sim.id: sim for sim in load_emails()}
FIVE = {"lookalike_domain", "urgency", "credential_request", "suspicious_url", "brand_impersonation"}

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_links(monkeypatch):
    monkeypatch.setattr(rewrite, "_store", rewrite.InMemoryLinkStore())
    monkeypatch.setattr(rewrite, "_on_click", rewrite.log_click)
    monkeypatch.setattr(rewrite, "recorded_clicks", [])


def upload(raw: bytes, name="message.eml"):
    return client.post("/api/analyze/signals", files={"file": (name, raw, "message/rfc822")})


def path_of(url: str) -> str:
    return urlsplit(url).path


def test_upload_returns_message_and_signals():
    response = upload(render_eml(BY_ID["cmp-01"]))
    assert response.status_code == 200
    body = response.json()
    assert body["message"]["sender"] == "security@micr0soft-verify.example"
    assert body["message"]["id"].startswith("eml-")
    assert FIVE <= {signal["category"] for signal in body["signals"]}
    assert body["unchecked"] == []
    assert all(signal["evidence"] and signal["technical_detail"] for signal in body["signals"])


def test_legitimate_upload_has_no_signals():
    body = upload(render_eml(BY_ID["leg-01"])).json()
    assert body["signals"] == []


@pytest.mark.parametrize("raw", [b"", b"hello world\n", b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj"],
                         ids=["empty", "text", "pdf"])
def test_a_file_that_is_not_an_email_is_rejected(raw):
    response = upload(raw, name="notes.eml")
    assert response.status_code == 422
    assert "not an email" in response.json()["detail"]


def test_a_huge_file_is_rejected():
    response = upload(make_eml("x" * (MAX_UPLOAD_BYTES + 10)))
    assert response.status_code == 413


def test_click_round_trip_records_the_click_and_redirects_to_the_demo_page():
    copy = rewrite_links(message_from_sim(BY_ID["cmp-01"]), "e01")
    response = client.get(path_of(copy.urls[0].url), follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == (rewrite.DEMO_SITE_URL +
                                            "/micr0soft-verify.example/verify?session=7f3a00c9")
    (event,) = rewrite.recorded_clicks
    assert (event.type, event.employee_id, event.message_id) == ("link_clicked", "e01", "cmp-01")


def test_a_real_website_is_blocked_but_the_click_is_still_recorded():
    message = parse_eml(make_eml("Sign in at https://www.realbank.com/login now"))
    copy = rewrite_links(message, "e02")
    response = client.get(path_of(copy.urls[0].url), follow_redirects=False)

    assert response.status_code == 200
    assert "location" not in response.headers
    assert "Link blocked" in response.text and "www.realbank.com" in response.text
    assert len(rewrite.recorded_clicks) == 1


def test_unknown_token_is_a_friendly_404():
    response = client.get("/r/not-a-token", follow_redirects=False)
    assert response.status_code == 404
    assert "not available" in response.text
    assert rewrite.recorded_clicks == []


def test_demo_placeholder_is_labelled_and_has_no_form():
    response = client.get("/demo/micr0soft-verify.example/verify")
    assert response.status_code == 200
    assert "SIMULATION" in response.text and "micr0soft-verify.example" in response.text
    assert "<form" not in response.text.lower()


def test_demo_placeholder_escapes_the_address_and_refuses_real_domains():
    response = client.get("/demo/%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E.test/a")
    assert response.status_code == 200
    assert "<img" not in response.text and "&lt;img src=x onerror=alert(1)&gt;.test" in response.text
    assert client.get("/demo/www.microsoft.com/login").status_code == 404
