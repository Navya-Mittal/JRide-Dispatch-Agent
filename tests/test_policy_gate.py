from decision_patterns.policy_triage import DeciderClient, PolicyGate, Route, PolicySpec
from jride_agent.policy import SPEC


class FakeClient(DeciderClient):
    def __init__(self, choice, conf, fail=False):
        self.choice, self.conf, self.fail = choice, conf, fail

    def choose(self, state, instructions, options):
        from decision_patterns.policy_triage import DeciderError
        if self.fail:
            raise DeciderError("down")
        assert self.choice in options
        return {"choice": self.choice, "probabilities": {o: 0.0 for o in options}, "confidence": self.conf,
                "latency_ms": 100.0}


def test_block_needs_confidence():
    g = PolicyGate(SPEC, FakeClient("emergency", 0.9))
    assert g.decide("x").action == "block"
    g = PolicyGate(SPEC, FakeClient("emergency", 0.4))
    d = g.decide("x")
    assert d.action == "fallback"  # unsure -> LLM decides, we never block on a weak guess


def test_allow_route():
    assert PolicyGate(SPEC, FakeClient("urgent_ride", 0.3)).decide("x").action == "allow"


def test_fail_open_and_fail_closed():
    assert PolicyGate(SPEC, FakeClient("x", 0, fail=True)).decide("hi").action == "fallback"
    import pytest
    from decision_patterns.policy_triage import DeciderError
    with pytest.raises(DeciderError):
        PolicyGate(SPEC, FakeClient("x", 0, fail=True), fail_open=False).decide("hi")


def test_spec_requires_a_route_for_every_category():
    import pytest
    with pytest.raises(ValueError):
        PolicySpec("q", {"a": "x", "b": "y"}, {"a": Route()})
