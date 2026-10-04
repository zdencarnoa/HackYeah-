from app.campaigns import devdata

from .helpers import ingest, push_for


def wave1(client):
    """Ingest m1-m3; returns the campaign they form."""
    camp = None
    for m in devdata.campaign_messages(3):
        camp = ingest(client, m)
    return camp


def test_click_then_password_escalates_same_incident(ctx):
    client, published = ctx
    camp = wave1(client)
    r = client.post("/api/evidence", json={"kind": "link_clicked", "employee_id": "alice", "message_id": "m1"})
    inc = r.json()
    assert inc["severity"] == 2 and inc["campaign_id"] == camp["id"]
    assert published[-1][0] == "incident.created"

    r = client.post("/api/integrations/chrome/password-reuse",
                    json=push_for("alice@company.example", "micr0soft-verify.example"))
    assert r.json()["incident_id"] == inc["id"]
    assert published[-1][0] == "incident.escalated"
    assert client.get(f"/api/incidents/{inc['id']}").json()["severity"] == 3


def test_approved_login_domain_never_fires(ctx):
    client, published = ctx
    r = client.post("/api/integrations/chrome/password-reuse",
                    json=push_for("alice@company.example", "login.lakeside-logistics.example"))
    assert "ignored" in r.json()
    assert published == [] and client.get("/api/incidents").json() == []


def test_employee_report_joins_campaign_incident(ctx):
    client, _ = ctx
    wave1(client)
    client.post("/api/evidence", json={"kind": "link_clicked", "employee_id": "alice", "message_id": "m1"})
    r = client.post("/api/interactions", json={"message_id": "m3", "employee_id": "bob", "kind": "password"})
    body = r.json()
    assert body["incident"]["affected_employees"] == ["alice", "bob"]
    assert body["incident"]["severity"] == 3
    assert body["incident"]["timeline"][-1]["source"] == "reported"
    assert body["already_detected"] == []  # nothing automatic was seen for bob


def test_email_scored_opens_no_incident(ctx):
    client, published = ctx
    r = client.post("/api/evidence", json={"kind": "email_scored", "employee_id": "alice", "message_id": "m1", "risk": 2})
    assert r.json() is None and published[-1][0] == "message.scored"
