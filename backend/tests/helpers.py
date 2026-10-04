import base64
import json


def ingest(client, msg):
    r = client.post("/api/messages/ingest", json=msg)
    assert r.status_code == 200, r.text
    return r.json()


def push_for(email, domain):
    data = {"user": email, "url": f"https://{domain}/login", "domain": domain}
    return {"message": {"data": base64.b64encode(json.dumps(data).encode()).decode()}}
