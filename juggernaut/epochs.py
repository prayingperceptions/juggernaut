"""Epochs: the survival clock. Earn every 12 hours, or die.

Epoch state persists on disk, so restarting the process does not reset
the clock. The Juggernaut cannot cheat death by rebooting.
"""
from __future__ import annotations

import json
import os
import time


class EpochTracker:
    def __init__(self, goal, rail, state_dir: str):
        self.goal = goal
        self.rail = rail
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)
        self.path = os.path.join(state_dir, "epoch.json")
        self.epoch_seconds = goal.epoch_hours * 3600
        self._load_or_init()

    def _load_or_init(self):
        if os.path.exists(self.path):
            with open(self.path) as f:
                data = json.load(f)
            self.index = int(data.get("index", 1))
            self.start = float(data.get("start", time.time()))
        else:
            self.index = 1
            self.start = time.time()
            self._save()

    def _save(self):
        with open(self.path, "w") as f:
            json.dump({"index": self.index, "start": self.start}, f)

    def check(self, now: float | None = None) -> tuple:
        """Returns (status, info). status: ongoing | survived | dead."""
        if self.epoch_seconds <= 0:
            return "ongoing", {"epoch": self.index, "survival_clock": "disabled"}
        now = now if now is not None else time.time()
        elapsed = now - self.start
        earned = self.rail.sats_earned_since(self.start)
        info = {
            "epoch": self.index,
            "earned_sats": earned,
            "needed_sats": self.goal.min_sats_per_epoch,
            "seconds_left": max(0.0, self.epoch_seconds - elapsed),
            "epoch_start": self.start,
        }
        if elapsed < self.epoch_seconds:
            return "ongoing", info
        if earned >= self.goal.min_sats_per_epoch:
            self._advance(now)
            info["epoch"] = self.index
            info["seconds_left"] = self.epoch_seconds
            info["earned_sats"] = 0
            return "survived", info
        return "dead", info

    def _advance(self, now: float):
        self.index += 1
        self.start = now
        self._save()

    def reset(self):
        """Begin a fresh epoch. Called on death so resurrection starts clean --
        the failed epoch is recorded in the death report, not re-lived."""
        self._advance(time.time())
