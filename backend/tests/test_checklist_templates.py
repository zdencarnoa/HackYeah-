"""Pure-Python tests (run by run_pure_tests.py, no installs needed)."""
from app.incidents.checklist_templates import AREAS, HIGH, TEMPLATES, incident_type_for


def test_keys_unique_and_areas_valid():
    for name, items in TEMPLATES.items():
        keys = [i.key for i in items]
        assert len(keys) == len(set(keys)), name
        assert all(i.area in AREAS for i in items), name


def test_containment_items_need_approval_and_manual_items_do_not():
    for items in TEMPLATES.values():
        for i in items:
            assert i.needs_approval == (i.containment_kind is not None), i.key


def test_credential_checklist_grows_with_severity():
    at_high = {i.key for i in TEMPLATES["credential_phishing"] if i.min_severity <= HIGH}
    assert at_high == {"block_sender_domain", "quarantine_messages", "notify_users"}
    assert len(TEMPLATES["credential_phishing"]) == 7


def test_incident_type_heuristic():
    link = ("Verify", "Click here", ["https://x.example/a"])
    bank = ("Bank details changed", "Please use the new IBAN", [])
    pl = ("Zmiana", "Nowy numer konta do przelewu", [])
    none = ("Hello", "Nice weather", [])
    assert incident_type_for([link]) == "credential_phishing"
    assert incident_type_for([bank, bank]) == "invoice_fraud"
    assert incident_type_for([pl]) == "invoice_fraud"
    assert incident_type_for([none]) == "suspicious_email"
    assert incident_type_for([]) == "suspicious_email"
