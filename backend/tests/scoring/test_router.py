from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.detection import message_from_sim, render_eml
from app.detection.router import MAX_UPLOAD_BYTES
from app.scoring import analyze as analyze_module
from app.scoring.router import router
from app.simulation.seed import load_emails

BY_ID = {sim.id: sim for sim in load_emails()}

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def upload(raw: bytes):
    return client.post("/api/analyze", files={"file": ("message.eml", raw, "message/rfc822")})


def no_ml(monkeypatch):
    monkeypatch.setattr(analyze_module, "classify", lambda message: None)


def test_upload_returns_assessment(monkeypatch):
    no_ml(monkeypatch)
    body = upload(render_eml(BY_ID["cmp-01"])).json()
    assert body["risk"] == 2  # HIGH
    assert body["explanation"]["reasons"]
    assert "password" in body["recommended_action"]
    assert {s["category"] for s in body["signals"]} >= {"lookalike_domain", "credential_request"}


def test_json_message_route(monkeypatch):
    no_ml(monkeypatch)
    legit = next(sim for sim in BY_ID.values() if sim.scenario.label == "legitimate")
    response = client.post("/api/analyze/message", json=message_from_sim(legit).model_dump(mode="json"))
    assert response.status_code == 200
    assert response.json()["risk"] == 0  # LOW


def test_rejects_non_email_and_huge_files(monkeypatch):
    no_ml(monkeypatch)
    assert upload(b"\x00\x01 not an email").status_code == 422
    assert upload(b"a" * (MAX_UPLOAD_BYTES + 1)).status_code == 413


def test_demo_assessments_cover_every_demo_email(monkeypatch):
    from app.scoring import router as router_module
    no_ml(monkeypatch)
    router_module.demo_assessments.cache_clear()
    body = client.get("/api/assessments").json()
    router_module.demo_assessments.cache_clear()
    assert set(body) == set(BY_ID)
    assert body["cmp-01"]["risk"] == 2 and body["amb-01"]["risk"] == 1
    assert all(body[i]["risk"] == 0 for i, sim in BY_ID.items()
               if sim.scenario.label == "legitimate" and i != "amb-01")
