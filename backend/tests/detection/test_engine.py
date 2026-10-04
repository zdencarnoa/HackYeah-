from app.detection import detect, engine, parse_eml
from app.schemas import DetectionResult, Signal
from tests.detection.helpers import make_eml


def signal(rule, category, severity):
    return Signal(id=rule, category=category, severity=severity, evidence="e",
                  technical_detail="t", source="rule")


def test_detect_merges_dedupes_and_orders_signals(monkeypatch):
    def first(message):
        return DetectionResult(signals=[signal("a.weak", "urgency", 1), signal("a.dup", "urgency", 1)],
                               unchecked=["We could not check A."])

    def second(message):
        return DetectionResult(signals=[signal("a.dup", "urgency", 2), signal("b.strong", "gift_card", 3),
                                        signal("b.other", "auth_failure", 3)])

    monkeypatch.setattr(engine, "CHECKS", [(first, "A"), (second, "B")])
    result = detect(parse_eml(make_eml()))
    assert [(s.id, s.severity) for s in result.signals] == [
        ("b.other", 3), ("b.strong", 3), ("a.dup", 2), ("a.weak", 1)]
    assert result.unchecked == ["We could not check A."]


def test_a_broken_check_does_not_break_detection(monkeypatch):
    def broken(message):
        raise RuntimeError("bug")

    def working(message):
        return DetectionResult(signals=[signal("ok", "urgency", 1)])

    monkeypatch.setattr(engine, "CHECKS", [(broken, "the broken thing"), (working, "the rest")])
    result = detect(parse_eml(make_eml()))
    assert [s.id for s in result.signals] == ["ok"]
    assert result.unchecked == ["We could not check the broken thing because of an internal error."]
