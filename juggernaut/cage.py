"""The cage. Ruthless inside bounds the user sets.

Hard rules:
- The brain only ever chooses from allowlisted actions (choice criteria).
- Anything irreversible needs human approval unless --auto-approve.
- The kill switch is a file: touch KILL and the agent dies on the next tick.
- The agent can never move funds out, spend, or exfiltrate keys:
  no such tool exists, so no such action is possible.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Cage:
    allowed_actions: list = field(default_factory=list)
    approvals_required: list = field(default_factory=list)
    max_ticks: int = 0  # 0 = unlimited
    kill_file: str = "KILL"
    auto_approve: bool = False

    def check(self, action_name: str) -> tuple:
        """Returns (ok, reason)."""
        if action_name not in self.allowed_actions:
            return False, f"'{action_name}' is not allowlisted — denied"
        if action_name in self.approvals_required and not self.auto_approve:
            return False, f"'{action_name}' needs human approval — skipped this tick"
        return True, "ok"

    def kill_requested(self) -> bool:
        return os.path.exists(self.kill_file)
