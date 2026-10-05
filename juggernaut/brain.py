"""The reflex layer. Laya answers three typed questions per tick, in ~30ms.

Real brain: laya-mlx (Apple Silicon, fully local, zero output tokens).
Fake brain: deterministic stand-in so the loop can be tested anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TickDecision:
    done_probability: float  # P(goal accomplished)
    action: str  # chosen tool name
    action_confidence: float
    progress_index: int  # zero-based rubric level
    progress_label: str


class Brain:
    def decide(self, state: str, goal, actions: list) -> TickDecision:
        raise NotImplementedError


class LayaBrain(Brain):
    """The real thing. Needs a Mac with Apple Silicon: pip install laya-mlx."""

    def __init__(self, model: str = "aac6fef/laya-mlx", dtype: str = "float16"):
        try:
            import laya_mlx as laya
        except ImportError as e:
            raise RuntimeError(
                "laya_mlx is not installed on this machine. "
                "On your Mac: pip install laya-mlx (Apple Silicon only)."
            ) from e
        self._laya = laya
        self.agent = laya.load(model, dtype=dtype)

    def decide(self, state: str, goal, actions: list) -> TickDecision:
        questions = {
            "done": {
                "type": "noul",
                "instructions": (
                    f"Single goal: {goal.objective}. "
                    f"Proposition: {goal.done_proposition} "
                    "Is the proposition true right now? Only true if fully accomplished."
                ),
            },
            "next_action": {
                "type": "choice",
                "instructions": (
                    f"Single goal: {goal.objective}. "
                    "Which ONE action best serves the goal right now? "
                    "Discard anything that does not directly serve the goal."
                ),
                "criteria": list(actions),
            },
            "progress": {
                "type": "score",
                "instructions": f"How close is this goal to accomplished: {goal.objective}",
                "criteria": goal.progress_rubric,
            },
        }
        result = self.agent.predict(state, questions)
        answers = result.get("answers", {})

        done_p = _coerce_probability(answers.get("done"))
        action_ans = answers.get("next_action")
        action = action_ans if isinstance(action_ans, str) else str(action_ans)
        action_conf = _coerce_confidence(action_ans)
        prog_idx, prog_label = _coerce_score(answers.get("progress"), goal.progress_rubric)

        if action not in actions:  # never trust, always verify
            action, action_conf = actions[0], 0.0
        return TickDecision(done_p, action, action_conf, prog_idx, prog_label)


class FakeBrain(Brain):
    """Deterministic stand-in for testing the loop without Apple Silicon.

    Cycles through actions in order, never declares done, progress creeps up.
    """

    def __init__(self):
        self._n = 0

    def decide(self, state: str, goal, actions: list) -> TickDecision:
        action = actions[self._n % len(actions)]
        self._n += 1
        idx = min(self._n // 3, len(goal.progress_rubric) - 1)
        return TickDecision(
            done_probability=0.0,
            action=action,
            action_confidence=0.9,
            progress_index=idx,
            progress_label=goal.progress_rubric[idx] if goal.progress_rubric else "",
        )


def _coerce_probability(ans) -> float:
    if isinstance(ans, bool):
        return 1.0 if ans else 0.0
    if isinstance(ans, (int, float)):
        return max(0.0, min(1.0, float(ans)))
    if isinstance(ans, dict):
        for k in ("p_true", "probability", "value"):
            if k in ans:
                return _coerce_probability(ans[k])
        if "true" in ans and "false" in ans:
            t = float(ans["true"])
            return t / max(t + float(ans["false"]), 1e-9)
    return 0.0


def _coerce_confidence(ans) -> float:
    if isinstance(ans, dict) and "answer_confidence" in ans:
        return _coerce_probability(ans["answer_confidence"])
    return 0.5


def _coerce_score(ans, rubric: list) -> tuple:
    idx = 0
    if isinstance(ans, (int, float)):
        idx = int(ans)
    elif isinstance(ans, dict):
        for k in ("level", "score", "value", "expected_level"):
            if k in ans and isinstance(ans[k], (int, float)):
                idx = int(ans[k])
                break
    idx = max(0, min(idx, len(rubric) - 1)) if rubric else 0
    label = rubric[idx] if rubric else ""
    return idx, label
