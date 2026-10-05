"""The single goal. Typed, non-negotiable, loaded from a mission file.

The Juggernaut holds exactly one goal. It cannot be given a second one.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Goal:
    name: str
    objective: str  # one sentence. The only thing that matters.
    done_proposition: str  # noul question: "is this true right now?"
    progress_rubric: list = field(default_factory=list)  # ordered score levels
    epoch_hours: float = 12.0  # survival window
    min_sats_per_epoch: int = 1  # earn at least this much per epoch, or die
    tick_seconds: int = 60  # seconds between ticks
    stall_ticks: int = 20  # no progress for this long -> escalate
    max_ticks: int = 0  # 0 = unlimited

    @classmethod
    def from_json(cls, path: str) -> "Goal":
        with open(path) as f:
            data = json.load(f)
        return cls(**data)
