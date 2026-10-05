"""Epoch survival clock: earn every epoch, or die."""
import os
import tempfile
import time

from juggernaut.epochs import EpochTracker
from juggernaut.goal import Goal
from juggernaut.rails.simulator import SimulatorRail


def make_goal(**kw):
    base = dict(name="t", objective="o", done_proposition="d",
                progress_rubric=["a", "b"])
    base.update(kw)
    return Goal(**base)


def test_ongoing_then_survived():
    d = tempfile.mkdtemp()
    g = make_goal(epoch_hours=0.0006, min_sats_per_epoch=1)  # ~2.2s
    rail = SimulatorRail(schedule=[(1.0, 250, "sim")])
    ep = EpochTracker(g, rail, d)
    assert ep.check()[0] == "ongoing"
    time.sleep(2.6)
    status, info = ep.check()
    assert status == "survived"
    assert info["epoch"] == 2


def test_starved_dies():
    d = tempfile.mkdtemp()
    g = make_goal(epoch_hours=0.0003, min_sats_per_epoch=1)  # ~1.1s
    ep = EpochTracker(g, SimulatorRail(), d)
    time.sleep(1.5)
    status, info = ep.check()
    assert status == "dead"
    assert info["earned_sats"] == 0


def test_reset_starts_fresh_epoch():
    d = tempfile.mkdtemp()
    g = make_goal(epoch_hours=0.0003, min_sats_per_epoch=1)
    ep = EpochTracker(g, SimulatorRail(), d)
    time.sleep(1.5)
    assert ep.check()[0] == "dead"
    ep.reset()
    status, info = ep.check()
    assert status == "ongoing" and info["epoch"] == 2


def test_disabled_clock_always_ongoing():
    d = tempfile.mkdtemp()
    g = make_goal(epoch_hours=0, min_sats_per_epoch=0)
    ep = EpochTracker(g, SimulatorRail(), d)
    time.sleep(0.1)
    status, info = ep.check()
    assert status == "ongoing"
    assert info["survival_clock"] == "disabled"


def test_epoch_survives_restart():
    d = tempfile.mkdtemp()
    g = make_goal(epoch_hours=1.0, min_sats_per_epoch=1)
    ep1 = EpochTracker(g, SimulatorRail(), d)
    start = ep1.start
    ep2 = EpochTracker(g, SimulatorRail(), d)  # "reboot"
    assert ep2.start == start  # clock was not reset
    assert ep2.index == 1
