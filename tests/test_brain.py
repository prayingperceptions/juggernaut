"""Brain: FakeBrain cycles; coercion helpers are defensive."""
from juggernaut.brain import (
    FakeBrain,
    _coerce_confidence,
    _coerce_probability,
    _coerce_score,
)
from juggernaut.goal import Goal


def test_fake_brain_cycles_actions():
    g = Goal(name="t", objective="o", done_proposition="d",
             progress_rubric=["low", "high"])
    b = FakeBrain()
    actions = ["a", "b", "c"]
    seen = [b.decide("s", g, actions).action for _ in range(4)]
    assert seen == ["a", "b", "c", "a"]


def test_fake_brain_never_done():
    g = Goal(name="t", objective="o", done_proposition="d",
             progress_rubric=["low", "high"])
    d = FakeBrain().decide("s", g, ["a"])
    assert d.done_probability == 0.0


def test_coerce_probability():
    assert _coerce_probability(True) == 1.0
    assert _coerce_probability(0.7) == 0.7
    assert _coerce_probability({"true": 3.0, "false": 1.0}) == 0.75
    assert _coerce_probability("nonsense") == 0.0
    assert _coerce_probability(None) == 0.0


def test_coerce_score():
    assert _coerce_score(2, ["a", "b", "c"]) == (2, "c")
    assert _coerce_score(99, ["a", "b"]) == (1, "b")  # clamped
    assert _coerce_score({"level": 1}, ["a", "b"]) == (1, "b")


def test_coerce_confidence():
    assert _coerce_confidence({"answer_confidence": 0.8}) == 0.8
    assert _coerce_confidence("x") == 0.5


def test_goal_from_json(tmp_path):
    p = tmp_path / "m.json"
    p.write_text('{"name": "N", "objective": "O", "done_proposition": "D", '
                 '"progress_rubric": ["a"], "epoch_hours": 24}')
    g = Goal.from_json(str(p))
    assert g.name == "N" and g.epoch_hours == 24
