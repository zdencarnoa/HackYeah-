"""End-to-end HTTP walk through the demo scenario, against the dev app."""

import pytest
from fastapi.testclient import TestClient

ALICE = "e01"
ADMIN = "e15"
CAMPAIGN = "camp-ms-verify"


@pytest.fixture
def client():
    from app.simulation.dev_app import app
    from app.simulation.runtime import credentials, reset_demo

    reset_demo()
    credentials.unusual_sign_in_delay_seconds = 0  # no waiting in the test
    with TestClient(app) as client:
        yield client
    reset_demo()


def test_reset_returns_empty_status(client):
    status = client.post("/api/sim/reset").json()
    assert status["delivered_count"] == 0 and status["scenario"] is None


def test_unknown_scenario_is_404(client):
    assert client.post("/api/sim/attack/does-not-exist").status_code == 404


def test_full_scenario_from_attack_to_recovery(client):
    # 1. Launch, then step until Alice's first campaign email lands.
    assert client.post("/api/sim/attack/microsoft").json()["scenario"] == "microsoft"
    client.post("/api/sim/attack/control/pause")
    alice_campaign = None
    while alice_campaign is None:
        client.post("/api/sim/attack/control/step")
        inbox = client.get(f"/api/sim/inbox/{ALICE}").json()
        alice_campaign = next((m for m in inbox if m["id"] == "cmp-01"), None)

    # 2. Alice clicks: the phishing page shows inline.
    token = alice_campaign["links"][0]["token"]
    page = client.get(f"/r/{token}", follow_redirects=False)
    assert page.status_code == 200 and "SIMULATION" in page.text

    # 3. Alice submits a password on the unapproved domain.
    result = client.post(f"/r/{token}/submit", data={"entered": "1"})
    assert "simulated phishing page" in result.text.lower()

    # 4. Deliver the rest, then the admin contains the whole campaign.
    client.post("/api/sim/attack/microsoft", params={"speed": 1000})
    import time
    for _ in range(200):
        if client.get("/api/sim/attack/status").json()["running"] is False:
            break
        time.sleep(0.02)
    campaign_ids = [f"cmp-{n:02d}" for n in range(1, 15)]

    contain = client.post("/api/sim/containment", json={
        "action": "contain_campaign",
        "campaign_id": CAMPAIGN,
        "message_ids": campaign_ids,
        "employee_ids": [ALICE],
        "approved_by": ADMIN,
    })
    assert contain.status_code == 200
    assert all(item["simulated"] for item in contain.json())

    # 5. Recovery reflects the containment.
    recovery = client.get("/api/sim/recovery").json()
    tracks = {t["name"]: t["percent"] for t in recovery["tracks"]}
    assert tracks["Message containment"] == 100

    # 6. Blast radius for Alice is available.
    blast = client.get(f"/api/blast-radius/{ALICE}").json()
    assert blast["employee_id"] == ALICE and any(n["at_risk"] for n in blast["nodes"])


def test_containment_rejects_non_admin(client):
    alice_inbox = []
    while not alice_inbox:
        client.post("/api/sim/attack/control/step")
        alice_inbox = client.get(f"/api/sim/inbox/{ALICE}").json()
    response = client.post("/api/sim/containment", json={
        "action": "quarantine_messages",
        "message_ids": [alice_inbox[0]["id"]],
        "approved_by": ALICE,
    })
    assert response.status_code == 403
