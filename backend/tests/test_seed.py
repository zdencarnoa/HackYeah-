import re
from urllib.parse import urlparse

from app.simulation.seed import load_approved_logins, load_emails, load_org

CAMPAIGN = "camp-ms-verify"
SAFE_TLDS = (".example", ".test")


def domain_of(address: str) -> str:
    return address.rsplit("@", 1)[1]


def test_org_references_are_consistent():
    org = load_org()
    employee_ids = {e.id for e in org.employees}
    service_ids = {s.id for s in org.services}
    assert len(employee_ids) == len(org.employees)
    assert len(service_ids) == len(org.services)
    for e in org.employees:
        assert e.manager_id is None or e.manager_id in employee_ids
        assert set(e.access) <= service_ids
    for d in org.dependencies:
        assert d.source in service_ids and d.target in service_ids
    assert {a.service_id for a in load_approved_logins()} <= service_ids
    assert any(e.is_admin for e in org.employees)


def test_email_ids_unique_and_recipients_known():
    emails = load_emails()
    org = load_org()
    known = {e.email for e in org.employees} | {f"all@{org.domain}"}
    assert len({m.id for m in emails}) == len(emails)
    for m in emails:
        assert set(m.to) <= known, m.id


def test_only_reserved_domains_are_used():
    hosts = [domain_of(m.sender_address) for m in load_emails()]
    hosts += [domain_of(m.reply_to) for m in load_emails() if m.reply_to]
    hosts += [urlparse(u).hostname for m in load_emails() for u in m.urls]
    hosts += [a.domain for a in load_approved_logins()]
    for host in hosts:
        assert host.endswith(SAFE_TLDS), host
    for m in load_emails():
        for word in re.findall(r"https?://([^/\s]+)", m.body_text):
            assert word.endswith(SAFE_TLDS), (m.id, word)


def test_demo_campaign_matches_the_script():
    """idea.md §19-20: 14 messages, 7 recipients, 3 departments, Alice targeted first."""
    by_email = {e.email: e for e in load_org().employees}
    campaign = [m for m in load_emails() if m.scenario.campaign_id == CAMPAIGN]
    recipients = {r for m in campaign for r in m.to}
    assert len(campaign) == 14
    assert len(recipients) == 7
    assert len({by_email[r].department for r in recipients}) == 3
    assert campaign[0].to == ["alice.johnson@lakeside-logistics.example"]
    assert {domain_of(m.sender_address) for m in campaign} == {"micr0soft-example.test"}
    assert {urlparse(u).hostname for m in campaign for u in m.urls} == {"login.micr0soft-example.test"}


def test_dataset_has_both_classes():
    labels = [m.scenario.label for m in load_emails()]
    assert labels.count("legitimate") >= 10
    assert labels.count("phishing") >= 14
