"""Full demo through the real UI (headless Chromium), against the live backend.

    pip install playwright && python -m playwright install chromium   # once
    python scripts/ui_demo_test.py   # backend :8000 and frontend :3000 (live mode) running

Steps follow the demo script; every step is checked, screenshotted and any browser
console error is collected. Run with backend :8000 and frontend :3000 up.
"""
import os
import sys
import tempfile
import time

import httpx
from playwright.sync_api import sync_playwright

API, UI = "http://localhost:8000", "http://localhost:3000"
OUT = os.environ.get("UI_TEST_OUT") or tempfile.mkdtemp(prefix="ui-demo-")
results, errors = [], []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'OK ' if ok else 'XX '} {name}" + (f"  ({detail})" if detail else ""), flush=True)


def shot(page, name):
    page.screenshot(path=f"{OUT}/{name}.png")


def incidents():
    return httpx.get(f"{API}/api/incidents").json()


httpx.post(f"{API}/api/sim/reset")
with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pages = {}
    for name in ("user", "admin"):
        pg = ctx.new_page()
        pg.on("console", lambda m, n=name: m.type == "error" and errors.append(f"[{n}] {m.text[:240]}"))
        pg.on("pageerror", lambda e, n=name: errors.append(f"[{n} pageerror] {str(e)[:240]}"))
        pg.goto(f"{UI}/{name}", wait_until="networkidle")
        pages[name] = pg
    user, admin = pages["user"], pages["admin"]

    # 1. launch the attack from the admin demo bar and deliver everything
    admin.keyboard.press("d")
    admin.get_by_role("button", name="10×").click()
    admin.get_by_role("button", name="Launch attack").click()
    for _ in range(60):
        s = httpx.get(f"{API}/api/sim/attack/status").json()
        if s["delivered_count"] >= s["total_count"]:
            break
        admin.get_by_role("button", name="Next email").click()
        admin.wait_for_timeout(250)
    check("1. napad isporucen", s["delivered_count"] == s["total_count"], f"{s['delivered_count']}/{s['total_count']}")
    user.wait_for_timeout(2500)
    admin.wait_for_timeout(500)
    shot(user, "1_user_inbox")
    shot(admin, "1_admin_flagged")
    n_user = user.get_by_text("URGENT: Your account will be suspended").count()
    check("2. Alice vidi Microsoft phishing u inboxu", n_user > 0, f"{n_user} prikaza")
    check("3. admin vidi sumnjive mailove", admin.get_by_text("URGENT: Your account will be suspended").count() > 0)

    # 2. Alice opens the phishing email: risk card with B's LLM explanation
    user.get_by_text("URGENT: Your account will be suspended").first.click()
    user.wait_for_timeout(800)
    shot(user, "2_user_phishing_open")
    body = user.inner_text("body")
    check("4. kartica rizika s LLM objasnjenjem", "high-risk phishing attempt" in body.lower() or "very likely" in body.lower(),
          body[body.lower().find("phishing attempt") - 60: body.lower().find("phishing attempt") + 20].replace("\n", " ") if "phishing attempt" in body.lower() else "nema")

    # 3. Alice clicks the link -> fake sign-in page -> types a password
    link = user.locator("button, a").filter(has_text="micr0soft").first
    if link.count() == 0:
        link = user.locator("button, a").filter(has_text="Verify").first
    link.click()
    user.wait_for_timeout(1500)
    shot(user, "3_fake_login")
    check("5. lazna stranica za prijavu", "/demo/" in user.url, user.url)
    deadline = time.time() + 8
    while time.time() < deadline and not any(any(e["kind"] == "link_clicked" for e in i["evidence"]) for i in incidents()):
        time.sleep(0.5)
    inc = incidents()
    check("6. klik stigao do C-a: HIGH incident", any(i["severity"] >= 2 and any(e["kind"] == "link_clicked" for e in i["evidence"]) for i in inc),
          str([(i["type"], i["severity"]) for i in inc]))
    user.get_by_role("button", name="Next").click()  # two-step sign-in, like the real one
    user.wait_for_timeout(600)
    pwd = user.locator("input[type=password]").first
    pwd.fill("Summer2026!")
    shot(user, "3b_password_step")
    user.locator("form button[type=submit], form button").last.click()
    user.wait_for_timeout(1500)
    shot(user, "4_after_password")
    deadline = time.time() + 10
    while time.time() < deadline and not any(i["severity"] == 3 for i in incidents()):
        time.sleep(0.5)
    crit = [i for i in incidents() if i["severity"] == 3]
    check("7. lozinka: CRITICAL incident", bool(crit), str(sorted({e["kind"] for i in crit for e in i["evidence"]})))

    # 4. back in the inbox: the password notice belongs only to the clicked email
    user.goto(f"{UI}/user", wait_until="networkidle")
    user.wait_for_timeout(2000)
    banner = user.get_by_text("POTENTIAL ACCOUNT COMPROMISE")
    check("8a. Alice vidi banner o kompromitaciji racuna (scenarij, korak 5)", banner.count() > 0)
    user.get_by_text("Invoices now available in our new portal").first.click()  # a different flagged email in Alice's inbox
    user.wait_for_timeout(800)
    user.get_by_role("button", name="Is this safe?").first.click() if user.get_by_role("button", name="Is this safe?").count() else None
    user.wait_for_timeout(600)
    flow = user.locator('section[aria-label="What happened?"]')
    flow_text = flow.first.inner_text() if flow.count() else ""
    check("8b. 'What happened?' drugog maila NE tvrdi da je tu unesena lozinka",
          "entered your password" not in flow_text, f"sekcija prikazana: {flow.count() > 0}")
    shot(user, "5_user_other_email")

    # 5. admin: incident, campaign, blast radius, containment, recovery
    admin.wait_for_timeout(2500)
    shot(admin, "6_admin_incident_list")
    row = admin.get_by_text("Credential phishing").first
    check("9. admin vidi incident", row.count() > 0)
    row.click()
    admin.wait_for_timeout(1000)
    shot(admin, "7_admin_incident")
    for i, tab in enumerate(["Campaign", "Blast radius", "Containment", "Recovery"]):
        t = admin.get_by_role("tab", name=tab)
        if t.count() == 0:
            t = admin.get_by_role("button", name=tab)
        ok = t.count() > 0
        if ok:
            t.first.click()
            admin.wait_for_timeout(1200)
            shot(admin, f"8_{i}_{tab.replace(' ', '_').lower()}")
        check(f"10.{i} kartica '{tab}'", ok)
        if tab == "Containment" and ok:
            btn = admin.get_by_role("button", name="Contain campaign")
            if btn.count() == 0:
                btn = admin.locator("button").filter(has_text="Contain").first
            if btn.count():
                btn.first.click()
                admin.wait_for_timeout(2000)
                shot(admin, "9_contained")
            status = [i["status"] for i in incidents() if i["severity"] == 3]
            check("11. zadrzavanje kampanje: incident contained", "contained" in status, str(status))

    # 6. admin: a flagged email opens its details
    admin.goto(f"{UI}/admin", wait_until="networkidle")
    admin.wait_for_timeout(2500)
    admin.get_by_text("Invoices now available in our new portal").first.click()
    admin.wait_for_timeout(1000)
    shot(admin, "10_admin_email_detail")
    detail = admin.inner_text("body")
    check("12. detalji maila otvoreni (dvosmisleni = MEDIUM)", "MEDIUM" in detail.upper() and "portal" in detail.lower())

    browser.close()

print("\nKONZOLA:", "\n".join(dict.fromkeys(errors)) or "nema gresaka")
print(f"\nREZULTAT: {sum(results)}/{len(results)} koraka prolazi  (snimke: {OUT})")
sys.exit(0 if all(results) and not errors else 1)
