"""Simulator rail: scripted earnings for dry runs.

Schedule entries are (delay_seconds_from_start, sats, source).
Default schedule pays nothing -- the agent starves and dies,
which is the correct behavior to observe first.
"""
from __future__ import annotations

import time

from . import EarningsRail


class SimulatorRail(EarningsRail):
    def __init__(self, schedule: list | None = None):
        self.t0 = time.time()
        self.schedule = schedule or []
        self._events = [
            {"at": self.t0 + delay, "sats": sats, "source": source}
            for delay, sats, source in self.schedule
        ]

    def sats_earned_since(self, since_ts: float) -> int:
        now = time.time()
        return sum(
            e["sats"] for e in self._events if e["at"] >= since_ts and e["at"] <= now
        )

    def describe(self) -> str:
        return f"SimulatorRail({len(self._events)} scripted payments)"
