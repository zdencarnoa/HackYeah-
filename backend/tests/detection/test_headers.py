import pytest

from app.detection import detect, message_from_sim, parse_eml
from app.detection.headers import NO_AUTH_RESULTS, check_headers, read_auth_results
from app.schemas import SignalCategory
from app.simulation.seed import load_emails
from tests.detection.helpers import make_eml

MX = "mx.lakeside-logistics.example"
DMARC_NONE_NOTE = ("We could not confirm this email really comes from paperline-supp1ies.test, "
                   "because that domain publishes no DMARC policy.")
SENDER = "Paperline Supplies Billing <billing@paperline-supp1ies.test>"
EMAILS = load_emails()
BY_ID = {sim.id: sim for sim in EMAILS}
# amb-01 is deliberately ambiguous (MEDIUM), so it is not held to the "no strong signal" bar.
LEGIT = [sim for sim in EMAILS if sim.scenario.label == "legitimate" and sim.id != "amb-01"]
CAMPAIGN = [sim for sim in EMAILS if sim.scenario.campaign_id == "camp-ms-verify"]


def check(auth=None, top=None, **headers):
    """Header signals for a small email. `top` is prepended as the topmost
    Authentication-Results header, above the one from `auth`."""
    raw = make_eml(From=SENDER, Authentication_Results=auth, **headers)
    if top is not None:
        raw = f"Authentication-Results: {top}\n".encode() + raw
    return check_headers(parse_eml(raw))


def by_id(result):
    return {signal.id: signal for signal in result.signals}


@pytest.mark.parametrize(("auth", "severity", "evidence_start"), [
    (f"{MX}; spf=fail smtp.mailfrom=x; dkim=none; dmarc=fail header.from=x", 2,
     "The domain paperline-supp1ies.test could not confirm"),
    (f"{MX}; spf=fail smtp.mailfrom=x; dkim=pass; dmarc=pass", 2,
     "The server that delivered this email is not allowed"),
    (f"{MX}; spf=hardfail", 2, "The server that delivered this email is not allowed"),
    (f"{MX}; spf=softfail; dkim=none; dmarc=none", 1,
     "The server that delivered this email is probably not allowed"),
    (f"{MX}; spf=pass; dkim=fail header.d=x; dmarc=pass", 1, "The digital seal on this email is broken"),
    (f"{MX}; spf=pass; dkim=pass; dmarc=pass", None, None),
    (f"{MX}; spf=none; dkim=none; dmarc=none", None, None),
    (f"{MX}; spf=neutral; dkim=temperror; dmarc=permerror", None, None),
    (f"{MX}; spf=permerror; dkim=policy", None, None),
])
def test_auth_results_become_one_combined_signal(auth, severity, evidence_start):
    result = check(auth)
    assert result.unchecked == ([DMARC_NONE_NOTE] if "dmarc=none" in auth else [])
    signal = by_id(result).get("header.auth")
    if severity is None:
        assert signal is None
        return
    assert (signal.category, signal.severity, signal.source) == (SignalCategory.AUTH_FAILURE, severity, "rule")
    assert signal.evidence.startswith(evidence_start)


def test_auth_evidence_is_plain_language_and_detail_has_the_jargon():
    signal = by_id(check(f"{MX}; spf=softfail smtp.mailfrom=x; dkim=none; dmarc=fail header.from=x"))["header.auth"]
    assert signal.evidence == ("The domain paperline-supp1ies.test could not confirm that it sent this email, "
                               "so the sender address may be forged.")
    assert signal.technical_detail == f"spf=softfail; dkim=none; dmarc=fail (from {MX})"
    for jargon in ("spf", "dkim", "dmarc"):
        assert jargon not in signal.evidence.lower()


def test_topmost_header_wins_over_a_forged_lower_one():
    forged_pass = "evil.test; spf=pass; dkim=pass; dmarc=pass"
    signal = by_id(check(forged_pass, top=f"{MX}; spf=fail; dmarc=fail"))["header.auth"]
    assert signal.severity == 2
    # dkim is only in the lower header, so it fills the gap; per server in the detail.
    assert signal.technical_detail == f"spf=fail (from {MX}); dkim=pass (from evil.test); dmarc=fail (from {MX})"
    assert "header.auth" not in by_id(check(f"evil.test; spf=fail; dmarc=fail", top=f"{MX}; spf=pass; dmarc=pass"))


def test_comments_cannot_smuggle_in_a_result():
    auth = f"{MX}; spf=fail (domain of x; dmarc=pass@evil.test (nested) is not allowed) smtp.mailfrom=evil.test"
    assert read_auth_results([auth]) == {"spf": ("fail", MX)}
    assert read_auth_results([f"{MX}; dmarc=fail (p=REJECT; spf=pass) header.from=x"]) == {"dmarc": ("fail", MX)}


def test_one_valid_dkim_signature_is_enough():
    assert "header.auth" not in by_id(check(f"{MX}; dkim=fail header.d=a.test; dkim=pass header.d=b.test"))


@pytest.mark.parametrize("auth", [None, f"{MX}; none", "%%% ((( ;;; ===", ""])
def test_missing_or_unreadable_auth_results_are_unchecked_not_a_signal(auth):
    result = check(auth)
    assert "header.auth" not in by_id(result)
    assert result.unchecked == [NO_AUTH_RESULTS]


def test_header_without_server_name_is_still_read():
    assert read_auth_results(["spf=fail; dmarc=fail"]) == {"spf": ("fail", ""), "dmarc": ("fail", "")}
    signal = by_id(check("spf=fail; dmarc=fail"))["header.auth"]
    assert signal.technical_detail == "spf=fail; dmarc=fail"


def test_reply_to_on_another_domain():
    signal = by_id(check(Reply_To="sarah.mitchell.billing@freemail.test"))["header.reply_to"]
    assert (signal.category, signal.severity) == (SignalCategory.REPLY_TO_MISMATCH, 2)
    assert signal.evidence == ("If you reply, your answer goes to sarah.mitchell.billing@freemail.test, "
                               "not to paperline-supp1ies.test, where the email claims to come from.")
    assert signal.technical_detail == ("Reply-To: sarah.mitchell.billing@freemail.test; "
                                       "From: billing@paperline-supp1ies.test")


@pytest.mark.parametrize("reply_to", [None, "billing@paperline-supp1ies.test",
                                      "invoices@accounts.paperline-supp1ies.test", "not an address"])
def test_reply_to_on_the_same_domain_or_missing_is_fine(reply_to):
    assert "header.reply_to" not in by_id(check(Reply_To=reply_to))


def test_no_mismatch_signal_without_a_sender():
    result = check_headers(parse_eml(make_eml(From=None, Reply_To="x@freemail.test",
                                              Return_Path="<bounce@mailer.test>")))
    assert result.signals == []


def test_return_path_on_another_domain_is_weak():
    signal = by_id(check(Return_Path="<bounce-123@mailer.sendgrid.test>"))["header.return_path"]
    assert (signal.category, signal.severity) == (SignalCategory.RETURN_PATH_MISMATCH, 1)
    assert signal.evidence.startswith("Error reports for this email go to mailer.sendgrid.test rather than "
                                      "paperline-supp1ies.test")


@pytest.mark.parametrize("return_path", ["<>", "<bounces@mail.paperline-supp1ies.test>", "garbage"])
def test_return_path_empty_or_same_domain_is_fine(return_path):
    assert "header.return_path" not in by_id(check(Return_Path=return_path))


@pytest.mark.parametrize("sim", LEGIT, ids=lambda sim: sim.id)
def test_legitimate_demo_mail_has_no_strong_header_signal(sim):
    result = check_headers(message_from_sim(sim))
    assert all(signal.severity < 2 for signal in result.signals), [s.evidence for s in result.signals]
    assert result.unchecked == []


@pytest.mark.parametrize("sim", CAMPAIGN, ids=lambda sim: sim.id)
def test_microsoft_campaign_passes_authentication(sim):
    assert "header.auth" not in by_id(check_headers(message_from_sim(sim)))


def test_mfa_scam_fails_authentication():
    signal = by_id(check_headers(message_from_sim(BY_ID["phi-03"])))["header.auth"]
    assert (signal.category, signal.severity) == (SignalCategory.AUTH_FAILURE, 2)
    assert "lakeside-it-support.test" in signal.evidence
    assert signal.technical_detail == f"spf=softfail; dkim=none; dmarc=fail (from {MX})"


def test_invoice_fraud_replies_go_to_free_mail():
    signal = by_id(check_headers(message_from_sim(BY_ID["phi-01"])))["header.reply_to"]
    assert signal.category == SignalCategory.REPLY_TO_MISMATCH
    assert "sarah.mitchell.billing@freemail.test" in signal.evidence


def test_detect_includes_header_signals():
    result = detect(message_from_sim(BY_ID["phi-03"]))
    assert "header.auth" in {signal.id for signal in result.signals}
    assert NO_AUTH_RESULTS not in result.unchecked
