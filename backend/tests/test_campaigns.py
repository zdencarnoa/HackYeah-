from datetime import datetime, timezone

from app.campaigns import devdata

from .helpers import ingest


def test_wave1_forms_a_campaign_only_from_the_second_message(ctx):
    client, published = ctx
    m = devdata.campaign_messages(3)
    assert ingest(client, m[0]) is None  # one message is not a campaign
    camp = ingest(client, m[1])
    assert camp["message_ids"] == ["m1", "m2"]
    assert published[-1][0] == "campaign.updated"
    camp = ingest(client, m[2])
    assert len(camp["message_ids"]) == 3 and len(camp["recipients"]) == 3


def test_full_demo_campaign_numbers(ctx):
    client, _ = ctx
    for m in devdata.campaign_messages(14):
        camp = ingest(client, m)
    assert len(camp["message_ids"]) == 14
    assert len(camp["recipients"]) == 7
    assert camp["departments"] == ["Finance", "HR", "Operations"]
    assert any("Same link target in all 14 messages" in t for t in camp["shared_traits"])
    assert len(client.get("/api/campaigns").json()) == 1


def test_legit_and_low_risk_mail_never_clusters(ctx):
    client, _ = ctx
    for m in devdata.campaign_messages(3):
        ingest(client, m)
    assert ingest(client, devdata.legit_invoice()) is None
    assert "ok1" not in client.get("/api/campaigns").json()[0]["message_ids"]


def test_invoice_fraud_is_a_separate_campaign(ctx):
    client, _ = ctx
    for m in devdata.campaign_messages(3):
        ingest(client, m)
    for m in devdata.invoice_fraud_messages():
        ingest(client, m)
    camps = client.get("/api/campaigns").json()
    assert len(camps) == 2
    assert sorted(len(c["message_ids"]) for c in camps) == [3, 3]


def test_click_before_correlation_gets_linked_to_the_campaign(ctx):
    client, _ = ctx
    m = devdata.campaign_messages(3)
    ingest(client, m[0])
    inc = client.post("/api/evidence", json={"kind": "link_clicked", "employee_id": "alice", "message_id": "m1"}).json()
    assert inc["campaign_id"] is None
    camp = ingest(client, m[1])
    assert client.get(f"/api/incidents/{inc['id']}").json()["campaign_id"] == camp["id"]
    assert camp["incident_id"] == inc["id"]


def test_two_incidents_merge_when_a_bridging_message_arrives(ctx):
    client, published = ctx
    now = datetime.now(timezone.utc).isoformat()

    def msg(i, to, sender, host, body):
        return {"id": i, "sender": sender, "recipient": f"{to}@company.example", "subject": f"Notice {i}",
                "body": body, "urls": [f"https://{host}/x"], "received_at": now, "risk": 2}

    x = msg("x", "alice", "a@one.example", "a.example", "alpha beta gamma delta epsilon zeta eta theta")
    y = msg("y", "bob", "b@two.example", "b.example", "iota kappa lambda mu nu xi omicron pi")
    z = msg("z", "carol", "b@two.example", "a.example", "rho sigma tau upsilon phi chi psi omega")
    assert ingest(client, x) is None and ingest(client, y) is None
    i1 = client.post("/api/evidence", json={"kind": "link_clicked", "employee_id": "alice", "message_id": "x"}).json()
    i2 = client.post("/api/evidence", json={"kind": "password_reuse", "employee_id": "bob", "message_id": "y",
                                            "domain": "b.example"}).json()
    assert i1["id"] != i2["id"]
    camp = ingest(client, z)  # shares a link target with x and a sender domain with y
    assert sorted(camp["message_ids"]) == ["x", "y", "z"]
    incidents = client.get("/api/incidents").json()
    assert len(incidents) == 1
    assert incidents[0]["severity"] == 3 and incidents[0]["affected_employees"] == ["alice", "bob"]
    assert published[-1][0] == "campaign.updated"


def test_unknown_recipient_is_rejected(ctx):
    client, _ = ctx
    bad = {**devdata.campaign_messages(1)[0], "recipient": "nobody@company.example"}
    assert client.post("/api/messages/ingest", json=bad).status_code == 422
