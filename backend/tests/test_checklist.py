from app.campaigns import devdata

from .helpers import ingest, push_for

CRED_AT_HIGH = {"block_sender_domain", "quarantine_messages", "notify_users"}
CRED_AT_CRITICAL = CRED_AT_HIGH | {"revoke_sessions", "reset_credentials",
                                   "review_account_activity", "write_report"}


def keys(inc):
    return {c["key"] for c in inc["checklist"]}


def item(inc, key):
    return next(c for c in inc["checklist"] if c["key"] == key)


def click(client):
    for m in devdata.campaign_messages(3):
        ingest(client, m)
    r = client.post("/api/evidence", json={"kind": "link_clicked", "employee_id": "alice", "message_id": "m1"})
    return r.json()


def password(client):
    r = client.post("/api/integrations/chrome/password-reuse",
                    json=push_for("alice@company.example", "micr0soft-verify.example"))
    return client.get(f"/api/incidents/{r.json()['incident_id']}").json()


def test_checklist_grows_with_severity(ctx):
    client, _ = ctx
    assert keys(click(client)) == CRED_AT_HIGH
    inc = password(client)
    assert keys(inc) == CRED_AT_CRITICAL
    assert [c["key"] for c in inc["checklist"]][:3] == ["block_sender_domain", "quarantine_messages", "notify_users"]
    assert all(c["rationale"] for c in inc["checklist"])


def test_containment_needs_approval_before_it_can_complete(ctx):
    client, published = ctx
    click(client)
    inc = password(client)
    step = item(inc, "revoke_sessions")
    assert step["needs_approval"] and step["containment_kind"] == "revoke_sessions"

    assert client.post(f"/api/checklist/{step['id']}/complete", json={}).status_code == 409
    r = client.post(f"/api/checklist/{step['id']}/approve", json={"approved_by": "admin"})
    assert r.status_code == 200 and item(r.json(), "revoke_sessions")["approved_by"] == "admin"
    r = client.post(f"/api/checklist/{step['id']}/complete", json={})
    assert r.status_code == 200 and item(r.json(), "revoke_sessions")["done"] is True
    assert "recovery.updated" in [t for t, _ in published]


def test_manual_steps_need_no_approval(ctx):
    client, _ = ctx
    click(client)
    inc = password(client)
    step = item(inc, "review_account_activity")
    assert not step["needs_approval"]
    assert client.post(f"/api/checklist/{step['id']}/approve", json={}).status_code == 409
    assert client.post(f"/api/checklist/{step['id']}/complete", json={}).status_code == 200
    reopened = client.post(f"/api/checklist/{step['id']}/complete", json={"done": False}).json()
    assert item(reopened, "review_account_activity")["done"] is False


def test_unknown_item_is_404(ctx):
    client, _ = ctx
    assert client.post("/api/checklist/nope/complete", json={}).status_code == 404


def test_approve_all_is_the_contain_campaign_button(ctx):
    client, _ = ctx
    click(client)
    inc = password(client)
    r = client.post(f"/api/incidents/{inc['id']}/approve-all", json={"approved_by": "admin"})
    assert r.status_code == 200
    pending = [c for c in r.json()["checklist"] if c["needs_approval"] and not c["approved_by"]]
    assert pending == []
    assert len([c for c in r.json()["checklist"] if c["needs_approval"]]) == 5
    assert not any(c["done"] for c in r.json()["checklist"])  # approval alone completes nothing


def test_progress_per_recovery_area(ctx):
    client, _ = ctx
    click(client)
    inc = password(client)
    for key in ("review_account_activity", "write_report"):
        client.post(f"/api/checklist/{item(inc, key)['id']}/complete", json={})
    p = client.get(f"/api/incidents/{inc['id']}/progress").json()
    assert p["areas"]["investigation"]["percent"] == 100
    assert p["areas"]["account"]["percent"] == 0
    assert p["percent"] == round(100 * 2 / 7)
    assert len(p["remaining"]) == 5


def test_dashboard_tiles(ctx):
    client, _ = ctx
    assert client.get("/api/dashboard").json()["open_incidents"] == 0
    click(client)
    password(client)
    d = client.get("/api/dashboard").json()
    assert d["open_incidents"] == 1 and d["by_severity"]["CRITICAL"] == 1
    assert d["active_campaigns"] == 1 and d["affected_employees"] == 1
    assert d["pending_approvals"] == 5 and d["checklist_total"] == 7 and d["checklist_done"] == 0
    assert d["latest_critical_incident_id"]


def test_summary_and_notification_fall_back_to_templates(ctx):
    client, _ = ctx
    click(client)
    inc = password(client)
    s = client.get(f"/api/incidents/{inc['id']}/summary").json()
    assert s["source"] == "template" and "credential phishing" in s["text"].lower()
    n = client.get(f"/api/incidents/{inc['id']}/notification/alice").json()
    assert "password" in n["text"].lower() and n["source"] == "template"
    assert client.get(f"/api/incidents/{inc['id']}/notification/bob").status_code == 404


def test_invoice_fraud_opens_a_medium_incident_at_three_messages(ctx):
    client, published = ctx
    msgs = devdata.invoice_fraud_messages()
    ingest(client, msgs[0])
    ingest(client, msgs[1])
    assert client.get("/api/incidents").json() == []
    ingest(client, msgs[2])
    incs = client.get("/api/incidents").json()
    assert len(incs) == 1
    inc = incs[0]
    assert inc["type"] == "invoice_fraud" and inc["severity"] == 1
    assert inc["affected_employees"] == ["dan", "erin", "hank"]
    assert {"confirm_by_phone", "hold_payments", "quarantine_messages"} <= keys(inc)
    assert "revoke_sessions" not in keys(inc)
    assert "incident.created" in [t for t, _ in published]


def test_password_event_is_never_swallowed_by_an_invoice_incident(ctx):
    client, _ = ctx
    for m in devdata.campaign_messages(3):  # alice is in the credential campaign
        ingest(client, m)
    fraud = devdata.invoice_fraud_messages()
    fraud[0]["recipient"] = "alice@company.example"  # ...and also receives invoice fraud
    for m in fraud:
        ingest(client, m)
    invoice = next(i for i in client.get("/api/incidents").json() if i["type"] == "invoice_fraud")
    r = client.post("/api/integrations/chrome/password-reuse",
                    json=push_for("alice@company.example", "micr0soft-verify.example"))
    assert r.json()["incident_id"] != invoice["id"]
    mine = client.get(f"/api/incidents/{r.json()['incident_id']}").json()
    assert mine["type"] == "credential_phishing" and mine["severity"] == 3
    assert mine["affected_employees"] == ["alice"]
