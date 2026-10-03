"""Pure-Python tests: need no FastAPI, SQLAlchemy or pydantic."""
from datetime import datetime, timedelta, timezone

from app.campaigns import devdata
from app.campaigns.matching import (
    JOIN_SCORE, campaign_name, features, pair_score, shared_traits, text_similarity,
)


def feats(msgs):
    return [features(m["id"], m["sender"], m["subject"], m["body"], m["urls"],
                     datetime.fromisoformat(m["received_at"])) for m in msgs]


def test_campaign_variants_all_join_each_other():
    f = feats(devdata.campaign_messages())
    for a in f:
        for b in f:
            if a is not b:
                assert pair_score(a, b)[0] >= JOIN_SCORE


def test_unrelated_messages_do_not_join():
    ms = feats(devdata.campaign_messages(1)) + feats(devdata.invoice_fraud_messages()) + feats([devdata.legit_invoice()])
    phish, rest = ms[0], ms[1:]
    for r in rest:
        assert pair_score(phish, r)[0] < JOIN_SCORE


def test_invoice_fraud_forms_its_own_campaign_by_sender_domain():
    a, b, c = feats(devdata.invoice_fraud_messages())
    assert pair_score(a, b)[0] >= JOIN_SCORE  # same sender domain, different mailbox


def test_freemail_and_shortener_do_not_count():
    now = datetime.now(timezone.utc)
    a = features("a", "x@gmail.com", "Win", "alpha beta gamma", ["https://bit.ly/aaa"], now)
    b = features("b", "y@gmail.com", "Prize", "delta epsilon zeta", ["https://bit.ly/bbb"], now)
    assert pair_score(a, b)[0] == 0


def test_time_window():
    now = datetime.now(timezone.utc)
    m = devdata.campaign_messages(2, start=now)
    a, b = feats(m)
    b2 = features(b.id, b.sender, "s", "x", ["https://micr0soft-verify.example/login?id=9"], now + timedelta(days=3))
    assert pair_score(a, b2)[0] == 0


def test_traits_for_full_campaign_are_readable_and_not_overclaiming():
    traits = shared_traits(feats(devdata.campaign_messages()))
    print(*traits, sep="\n")
    assert any("Same link target in all 14 messages: micr0soft-verify.example" in t for t in traits)
    assert any("Same sender domain in all 14 messages: micr0soft-verify.example" in t for t in traits)
    assert any(t.startswith("Similar wording") for t in traits)
    assert any(t.startswith("All delivered within") for t in traits)
    assert campaign_name(feats(devdata.campaign_messages())) == "Suspicious emails from micr0soft-verify.example"


def test_single_message_has_no_traits():
    assert shared_traits(feats(devdata.campaign_messages(1))) == []
