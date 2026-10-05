"""Juggernaut CLI.

Dry run (any machine, fake brain + scripted earnings, nothing real):
    juggernaut --mission missions/sats_or_death.json --dry-run --ticks 40

Live run (Mac with Apple Silicon):
    pip install "juggernaut-agent[brain]"
    juggernaut --mission missions/sats_or_death.json --auto-approve

Kill it: touch state/KILL
"""
from __future__ import annotations

import argparse
import json
import os

from . import __version__
from .agent import Juggernaut
from .brain import FakeBrain, LayaBrain
from .cage import Cage
from .epochs import EpochTracker
from .goal import Goal
from .rails.ledger import LedgerRail
from .rails.simulator import SimulatorRail
from .tools import default_tools

DEFAULT_CONFIG = {
    "service_name": "juggernaut-service",
    "service_url": "",
    "pitch": "pay-per-call microservice, settled in sats",
    "price_ladder_sats": [1000, 500, 250, 100],
    "current_price_sats": 1000,
    "payout_address": "",
    "sweep_threshold_sats": 1000,
    "sweep_mode": "manual",
}


def load_config(state_dir: str) -> tuple:
    path = os.path.join(state_dir, "hustle.json")

    def save(cfg):
        with open(path, "w") as f:
            json.dump(cfg, f, indent=2)

    if os.path.exists(path):
        with open(path) as f:
            cfg = json.load(f)
        # backfill new keys on old configs
        changed = False
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
                changed = True
        if changed:
            save(cfg)
        return cfg, save
    cfg = dict(DEFAULT_CONFIG)
    save(cfg)
    return cfg, save


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Juggernaut: one goal, or die.")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("--mission", required=True, help="path to mission JSON")
    ap.add_argument("--state-dir", default="state",
                    help="working dir for ledger/epochs/reports")
    ap.add_argument("--rail", choices=["simulator", "ledger"], default="ledger")
    ap.add_argument("--brain", choices=["laya", "fake"], default="laya")
    ap.add_argument("--dry-run", action="store_true",
                    help="fake brain + simulator rail, no sleeping")
    ap.add_argument("--ticks", type=int, default=0, help="max ticks (0 = unlimited)")
    ap.add_argument("--epoch-minutes", type=float, default=0,
                    help="override epoch length in minutes (testing)")
    ap.add_argument("--sim-pays", action="store_true",
                    help="simulator scripts a payment so the agent survives (dry-run)")
    ap.add_argument("--auto-approve", action="store_true",
                    help="allow approval-gated actions without a human")
    ap.add_argument("--no-sleep", action="store_true", help="don't sleep between ticks")
    ap.add_argument("--port", type=int, default=8787,
                    help="ledger webhook port (0 = off)")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)

    goal = Goal.from_json(args.mission)
    if args.epoch_minutes:
        goal.epoch_hours = args.epoch_minutes / 60.0
    if args.dry_run:
        goal.tick_seconds = 0

    state_dir = os.path.abspath(args.state_dir)
    os.makedirs(state_dir, exist_ok=True)
    config, save_config = load_config(state_dir)

    if args.dry_run or args.rail == "simulator":
        schedule = [(3, 250, "sim-patron")] if args.sim_pays else []
        rail = SimulatorRail(schedule=schedule)
    else:
        rail = LedgerRail(state_dir, port=args.port)
        print(f"[juggernaut] earnings webhook: POST http://127.0.0.1:{args.port}/earn")

    brain = FakeBrain() if (args.dry_run or args.brain == "fake") else LayaBrain()

    tools = default_tools()
    approvals = [t.name for t in tools if t.needs_approval]
    if config.get("sweep_mode") == "auto":
        # user pre-authorized the sweep rule in hustle.json -- the cage honors it
        approvals = [a for a in approvals if a != "sweep_funds"]
    cage = Cage(
        allowed_actions=[t.name for t in tools],
        approvals_required=approvals,
        max_ticks=args.ticks,
        kill_file=os.path.join(state_dir, "KILL"),
        auto_approve=args.auto_approve,
    )
    epoch = EpochTracker(goal, rail, state_dir)

    jug = Juggernaut(goal, brain, cage, epoch, rail, tools, state_dir,
                     config, save_config, no_sleep=args.no_sleep or args.dry_run)
    jug.run()
