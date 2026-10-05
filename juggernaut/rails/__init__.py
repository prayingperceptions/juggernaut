"""Earnings rails: how the Juggernaut knows money arrived.

Only net-new sats from EXTERNAL sources count. The agent has no tool
that can move funds, so it cannot fake earnings by paying itself.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class EarningsRail(ABC):
    @abstractmethod
    def sats_earned_since(self, since_ts: float) -> int:
        """Net-new sats from external sources settled at/after since_ts."""

    def describe(self) -> str:
        return self.__class__.__name__
