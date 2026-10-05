"""The reflex layer. Laya answers three typed questions per tick, in ~30ms.

Real brain: laya-mlx (Apple Silicon, fully local, zero output tokens).
Fake brain: deterministic stand-in so the loop can be tested anywhere.

Set JUGGERNAUT_DEBUG=1 to print raw Laya answers on every tick.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

DEBUG = os.environ.get("JUGGERNAUT_DEBUG") == "1"


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
        if DEBUG:
            print("[brain] raw:", json.dumps(answers, default=str)[:1500], flush=True)

        done_p = _coerce_probability(answers.get("done"))
        action, action_conf = _extract_choice(answers.get("next_action"), actions)
        prog_idx, prog_label = _coerce_score(answers.get("progress"), goal.progress_rubric)
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


def _extract_choice(ans, actions: list) -> tuple:
    """Pull (label, confidence) out of a choice answer in any plausible shape,
    then match it against the action list. Never returns an unmatched label."""
    label, conf = None, 0.5
    if isinstance(ans, str):
        label = ans
    elif isinstance(ans, dict):
        for k in ("answer", "label", "value", "choice", "selected"):
            if isinstance(ans.get(k), str):
                label = ans[k]
                break
        for k in ("answer_confidence", "confidence", "probability", "p"):
            if isinstance(ans.get(k), (int, float)):
                conf = _coerce_probability(ans[k])
                break
        if label is None and len(ans) == 1:
            # single-entry {label: prob} shape
            only = next(iter(ans))
            if isinstance(only, str):
                label = only
                v = ans[only]
                if isinstance(v, (int, float)):
                    conf = _coerce_probability(v)
    if not isinstance(label, str):
        label = str(ans) if ans is not None else ""

    norm = {a.strip().lower(): a for a in actions}
    matched = norm.get(label.strip().lower())
    if matched is None:
        return actions[0], 0.0  # never trust, always verify
    return matched, conf


def _coerce_probability(ans) -> float:
    if isinstance(ans, bool):
        return 1.0 if ans else 0.0
    if isinstance(ans, (int, float)):
        return max(0.0, min(1.0, float(ans)))
    if isinstance(ans, dict):
        if "answer" in ans:  # unwrap {"answer": ...} envelopes
            return _coerce_probability(ans["answer"])
        for k in ("p_true", "probability", "value"):
            if k in ans:
                return _coerce_probability(ans[k])
        if "true" in ans and "false" in ans:
            t = float(ans["true"])
            return t / max(t + float(ans["false"]), 1e-9)
    return 0.0


def _coerce_score(ans, rubric: list) -> tuple:
    idx = 0
    if isinstance(ans, bool):
        idx = int(ans)
    elif isinstance(ans, (int, float)):
        idx = int(ans)
    elif isinstance(ans, str):
        low = ans.strip().lower()
        for i, level in enumerate(rubric):
            if str(level).strip().lower() == low:
                idx = i
                break
    elif isinstance(ans, dict):
        if "answer" in ans:
            return _coerce_score(ans["answer"], rubric)
        for k in ("level", "score", "value", "expected_level"):
            if k in ans and isinstance(ans[k], (int, float)):
                idx = int(ans[k])
                break
    idx = max(0, min(idx, len(rubric) - 1)) if rubric else 0
    label = rubric[idx] if rubric else ""
    return idx, label
