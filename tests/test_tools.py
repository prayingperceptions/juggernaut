"""Tools: the hustle toolbox behaves."""
import json
import os
import tempfile
import time

from juggernaut.goal import Goal
from juggernaut.rails.simulator import SimulatorRail
from juggernaut.tools import (
    CheckEarnings,
    ProposeTactic,
    PublishListing,
    SetPrice,
    SweepFunds,
    default_tools,
)


def ctx(**kw):
    d = kw.pop("state_dir", tempfile.mkdtemp())
    base = {
        "goal": Goal(name="t", objective="o", done_proposition="d",
                     progress_rubric=["a", "b"], min_sats_per_epoch=1),
        "rail": SimulatorRail(),
        "epoch": type("E", (), {"start": time.time(), "index": 1})(),
        "state_dir": d,
        "config": {"payout_address": "", "sweep_threshold_sats": 1000,
                   "sweep_mode": "manual", "price_ladder_sats": [1000, 500, 250],
                   "current_price_sats": 1000},
        "save_config": lambda: None,
        "recent_ticks": lambda n: [],
    }
    base.update(kw)
    return base


def test_tool_names_unique():
    names = [t.name for t in default_tools()]
    assert len(names) == len(set(names))


def test_sweep_needs_address():
    out = SweepFunds().run(ctx())
    assert "no payout_address" in out


def test_sweep_writes_instruction_once():
    c = ctx(config={"payout_address": "bc1qtest", "sweep_threshold_sats": 1000,
                    "sweep_mode": "manual"})
    c["rail"] = SimulatorRail(schedule=[(0, 3000, "sim")])
    out = SweepFunds().run(c)
    assert "sweep instruction written" in out
    out2 = SweepFunds().run(c)
    assert "holding" in out2  # sweepable now 0 -- no double-sweep


def test_price_ladder_steps_down_and_floors():
    saved = {}
    c = ctx(save_config=lambda: saved.update(c["config"]))
    assert "1000 -> 500" in SetPrice().run(c)
    assert "500 -> 250" in SetPrice().run(c)
    assert "floor" in SetPrice().run(c)


def test_propose_tactic_writes_draft():
    c = ctx()
    out = ProposeTactic().run(c)
    assert "needs human approval" in out
    assert os.path.isdir(os.path.join(c["state_dir"], "tactics"))


def test_publish_listing():
    c = ctx()
    out = PublishListing().run(c)
    assert "listing.json" in out
    data = json.load(open(os.path.join(c["state_dir"], "listing.json")))
    assert data["price_sats"] == 1000


def test_check_earnings_reports():
    c = ctx()
    c["rail"] = SimulatorRail(schedule=[(0, 250, "sim")])
    out = CheckEarnings().run(c)
    assert "250 sats" in out
