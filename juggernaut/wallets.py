"""Payouts: forwarding earned sats to the user's Coinbase address.

The sweep rule lives in hustle.json and is set by the USER, never the agent:
  payout_address:       BTC receiving address (the user's Coinbase address)
  sweep_threshold_sats: sweep when sweepable >= this (default 1000)
  sweep_mode:           "manual" (default) | "auto"

Manual mode (default): SweepFunds writes a payout instruction to payouts/.
A human executes it, then flips status to "done". The agent never touches
keys and never moves funds by itself.

Auto mode: the user has pre-authorized the sweep rule AND configured a
backend holding keys. v1 ships no auto backend -- the interface below is
ready (see README "automating payouts": Alby Hub NWC for Lightning,
Boltz submarine swaps for Lightning -> on-chain BTC).
"""
from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod


class PayoutBackend(ABC):
    @abstractmethod
    def send(self, address: str, sats: int) -> str:
        """Broadcast the payout. Returns a txid / payment hash."""


class ManualBackend(PayoutBackend):
    def send(self, address: str, sats: int) -> str:
        raise RuntimeError(
            "no automated payout backend configured -- "
            "execute the instruction in payouts/ manually"
        )


def payouts_dir(state_dir: str) -> str:
    p = os.path.join(state_dir, "payouts")
    os.makedirs(p, exist_ok=True)
    return p


def total_swept(state_dir: str) -> int:
    """Sats already covered by payout instructions (pending or done)."""
    total = 0
    d = os.path.join(state_dir, "payouts")
    if not os.path.isdir(d):
        return 0
    for fn in os.listdir(d):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, fn)) as f:
                e = json.load(f)
            if e.get("status") in ("pending", "done"):
                total += int(e.get("sats", 0))
        except (json.JSONDecodeError, ValueError, KeyError):
            continue
    return total


def write_instruction(state_dir: str, address: str, sats: int) -> str:
    if not isinstance(sats, int) or sats <= 0:
        raise ValueError("sats must be a positive integer")
    entry = {
        "ts": time.time(),
        "address": address,
        "sats": int(sats),
        "status": "pending",
        "tx": "",
    }
    path = os.path.join(payouts_dir(state_dir), f"payout-{int(time.time())}.json")
    with open(path, "w") as f:
        json.dump(entry, f, indent=2)
    return path
