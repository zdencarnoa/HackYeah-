"""Run the whole loop against a running server:  python -m app.incidents.fake_flow
Open http://localhost:8000/api/events in a browser tab first to watch the events."""
import base64
import json
import time

import httpx

from app.campaigns import devdata

BASE = "http://localhost:8000"


def main() -> None:
    c = httpx.Client(base_url=BASE, timeout=5)
    c.post("/api/dev/reset-and-seed").raise_for_status()
    msgs = devdata.campaign_messages(14)

    def deliver(batch):
        for m in batch:
            camp = c.post("/api/messages/ingest", json=m).json()
        return camp

    camp = deliver(msgs[:3])
    print(f"wave 1 delivered -> campaign '{camp['name']}' with {len(camp['message_ids'])} messages")

    r = c.post("/api/evidence", json={"kind": "link_clicked", "employee_id": "alice", "message_id": "m1"})
    print("click ->", r.json()["severity"], "(HIGH=2)")
    time.sleep(1)

    event = {"user": "alice@company.example", "url": "https://micr0soft-verify.example/login",
             "domain": "micr0soft-verify.example"}
    push = {"message": {"data": base64.b64encode(json.dumps(event).encode()).decode()}}
    t0 = time.perf_counter()
    c.post("/api/integrations/chrome/password-reuse", json=push).raise_for_status()
    print(f"password reuse handled in {(time.perf_counter() - t0) * 1000:.0f} ms")

    r = c.post("/api/interactions", json={"message_id": "m1", "employee_id": "alice", "kind": "password"})
    print("already detected:", r.json()["already_detected"])

    camp = deliver(msgs[3:])  # waves 2-3
    print(f"campaign now: {len(camp['message_ids'])} messages, {len(camp['recipients'])} recipients, "
          f"{len(camp['departments'])} departments")
    for t in camp["shared_traits"]:
        print("  -", t)
    inc = c.get("/api/incidents").json()[0]
    print("incident severity:", inc["severity"], "(CRITICAL=3), campaign:", inc["campaign_id"])
    for t in inc["timeline"]:
        print("  -", t["source"], "|", t["text"])


if __name__ == "__main__":
    main()
