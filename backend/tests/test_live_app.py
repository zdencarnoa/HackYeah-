"""D5: the whole demo runs over HTTP on the live app (main.app), with every
router mounted and the pipeline wired at startup."""

import time

import pytest
from fastapi.testclient import TestClient

from app.db import session as db_session

ALICE = "e01"
ADMIN = "e15"


@pytest.fixture
def client():
    db_session.configure("sqlite://")  # fresh in-memory DB; lifespan seeds D's org
    db_session.init_db()
    from app.main import app
    with TestClient(app) as client:  # runs the lifespan: seed + wire_live
        yield client


def _run_attack_to_completion(client):
    client.post("/api/sim/reset")
    client.post("/api/sim/attack/microsoft", params={"speed": 1000})
    for _ in range(300):
        if client.get("/api/sim/attack/status").json()["running"] is False:
            return
        time.sleep(0.02)
    raise AssertionError("attack did not finish")


def test_simulation_routes_are_mounted(client):
    assert client.get("/api/sim/attack/status").status_code == 200
    assert client.get(f"/api/blast-radius/{ALICE}").status_code == 200


def test_full_demo_over_http(client):
    # Deliver the whole campaign; D1 scores each email and C correlates it.
    _run_attack_to_completion(client)
    inbox = client.get(f"/api/sim/inbox/{ALICE}").json()
    campaign = next(m for m in inbox if m["id"] == "cmp-01")

    # Alice clicks the link and submits a password on the fake page (D2).
    token = campaign["links"][0]["token"]
    assert client.get(f"/r/{token}", follow_redirects=False).status_code == 200
    client.post(f"/r/{token}/submit", data={"entered": "1"})

    # The admin sees a CRITICAL incident, before any employee report.
    incidents = client.get("/api/incidents").json()
    assert incidents, "no incident created"
    incident = incidents[0]
    assert incident["severity"] == 3 and incident["status"] == "open"

    # The admin contains the campaign (D4) -> the incident becomes contained.
    campaign_ids = [f"cmp-{n:02d}" for n in range(1, 15)]
    contain = client.post("/api/sim/containment", json={
        "action": "contain_campaign", "message_ids": campaign_ids,
        "employee_ids": [ALICE], "approved_by": ADMIN,
    })
    assert contain.status_code == 200 and all(r["simulated"] for r in contain.json())
    assert client.get("/api/incidents").json()[0]["status"] == "contained"

    # Recovery reflects the containment, and reset (D3) clears everything.
    tracks = {t["name"]: t["percent"] for t in client.get("/api/sim/recovery").json()["tracks"]}
    assert tracks["Message containment"] == 100
    assert client.post("/api/sim/reset").json()["delivered_count"] == 0
    assert client.get("/api/incidents").json() == []
