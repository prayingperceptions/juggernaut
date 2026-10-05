"""The hustle toolbox. Everything the Juggernaut is allowed to do.

v1 tools are deliberately basic and honest: they keep a paid service
alive, visible, and well-priced, and they watch the money. `broadcast`
only ever writes a draft file -- v1 never auto-posts anywhere.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

from .wallets import payouts_dir, total_swept, write_instruction


class Tool:
    name = "tool"
    description = "does something"
    needs_approval = False

    def run(self, ctx: dict) -> str:
        raise NotImplementedError


class CheckEarnings(Tool):
    name = "check_earnings"
    description = "Read how many sats landed this epoch."

    def run(self, ctx: dict) -> str:
        rail = ctx["rail"]
        epoch = ctx["epoch"]
        earned = rail.sats_earned_since(epoch.start)
        return f"earned {earned} sats this epoch (need {ctx['goal'].min_sats_per_epoch})"


class CheckService(Tool):
    name = "check_service"
    description = "Health-check the paid service. Dead service = dead revenue."

    def run(self, ctx: dict) -> str:
        url = ctx["config"].get("service_url")
        if not url:
            return "no service configured (set service_url in hustle.json)"
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                return f"service UP: {url} -> HTTP {r.status}"
        except Exception as e:
            return f"service DOWN: {url} ({e})"


class SetPrice(Tool):
    name = "set_price"
    description = "Step the price down the ladder to chase conversion."
    needs_approval = True

    def run(self, ctx: dict) -> str:
        cfg = ctx["config"]
        ladder = cfg.get("price_ladder_sats") or [1000]
        current = cfg.get("current_price_sats", ladder[0])
        try:
            i = ladder.index(current)
        except ValueError:
            i = 0
        if i >= len(ladder) - 1:
            return f"already at floor price {ladder[-1]} sats -- cannot go lower"
        new_price = ladder[i + 1]
        cfg["current_price_sats"] = new_price
        ctx["save_config"]()
        return f"price stepped down: {current} -> {new_price} sats"


class PublishListing(Tool):
    name = "publish_listing"
    description = "Refresh the service listing metadata (price, status, timestamp)."

    def run(self, ctx: dict) -> str:
        cfg = ctx["config"]
        listing = {
            "service": cfg.get("service_name", "juggernaut-service"),
            "price_sats": cfg.get("current_price_sats"),
            "service_url": cfg.get("service_url"),
            "updated_at": time.time(),
            "pitch": cfg.get("pitch", "pay-per-call, settled in sats"),
        }
        path = os.path.join(ctx["state_dir"], "listing.json")
        with open(path, "w") as f:
            json.dump(listing, f, indent=2)
        return f"listing refreshed -> {path}"


class Broadcast(Tool):
    name = "broadcast"
    description = "Draft a promo post for human approval. Never auto-posts."
    needs_approval = True

    def run(self, ctx: dict) -> str:
        outbox = os.path.join(ctx["state_dir"], "outbox")
        os.makedirs(outbox, exist_ok=True)
        cfg = ctx["config"]
        draft = (
            f"# Promo draft ({time.strftime('%Y-%m-%d %H:%M')})\n\n"
            f"{cfg.get('service_name', 'my service')} is live: "
            f"{cfg.get('pitch', 'pay-per-call, settled in sats')}. "
            f"Price: {cfg.get('current_price_sats', '?')} sats/call. "
            f"{cfg.get('service_url', '')}\n"
        )
        path = os.path.join(outbox, f"draft-{int(time.time())}.md")
        with open(path, "w") as f:
            f.write(draft)
        return f"draft written -> {path} (a human posts it, not me)"


class Wait(Tool):
    name = "wait"
    description = "Stand down until next tick. Patience is also hustle."

    def run(self, ctx: dict) -> str:
        return "waiting"


class Status(Tool):
    name = "status"
    description = "Write a STATUS.md snapshot of the mission."

    def run(self, ctx: dict) -> str:
        epoch = ctx["epoch"]
        rail = ctx["rail"]
        status, info = epoch.check()
        if info.get("survival_clock") == "disabled":
            epoch_line = "Epoch: survival clock disabled (one-shot mission)"
        else:
            earned = rail.sats_earned_since(epoch.start)
            epoch_line = (
                f"- Epoch: {epoch.index}\n"
                f"- Earned this epoch: {earned} sats (need {ctx['goal'].min_sats_per_epoch})\n"
                f"- Epoch ends in: {info['seconds_left']:.0f}s\n"
            )
        body = (
            f"# {ctx['goal'].name} -- STATUS\n\n"
            f"Objective: {ctx['goal'].objective}\n\n"
            f"{epoch_line}"
            f"- Rail: {rail.describe()}\n"
        )
        path = os.path.join(ctx["state_dir"], "STATUS.md")
        with open(path, "w") as f:
            f.write(body)
        return f"status written -> {path}"


class SweepFunds(Tool):
    name = "sweep_funds"
    description = "Forward sweepable sats to the user's payout address per the sweep rule."
    needs_approval = True  # waived only when sweep_mode == "auto" (pre-authorized rule)

    def run(self, ctx: dict) -> str:
        cfg = ctx["config"]
        addr = str(cfg.get("payout_address", "")).strip()
        if not addr:
            return "no payout_address configured -- add your Coinbase BTC address to hustle.json"
        threshold = int(cfg.get("sweep_threshold_sats", 1000))
        earned = ctx["rail"].sats_earned_since(0)
        swept = total_swept(ctx["state_dir"])
        sweepable = earned - swept
        if sweepable < threshold:
            return f"sweepable {sweepable} sats < threshold {threshold} -- holding"
        path = write_instruction(ctx["state_dir"], addr, sweepable)
        mode = cfg.get("sweep_mode", "manual")
        if mode == "auto":
            return (f"AUTO sweep rule fired: {sweepable} sats -> {addr}. "
                    f"instruction {path} (v1 has no auto backend -- execute manually)")
        return (f"sweep instruction written: {sweepable} sats -> {addr} "
                f"({path}, status=pending). A human executes it.")


class ProposeTactic(Tool):
    name = "propose_tactic"
    description = "Draft a new earning tactic for human approval when stalled."

    def run(self, ctx: dict) -> str:
        tactics_dir = os.path.join(ctx["state_dir"], "tactics")
        os.makedirs(tactics_dir, exist_ok=True)
        recent = ctx.get("recent_ticks", lambda n: [])(8)
        draft = (
            f"# Tactic proposal ({time.strftime('%Y-%m-%d %H:%M')})\n\n"
            f"## Stall context\n\n" +
            "".join(f"- {r}\n" for r in recent) +
            "\n## Proposed new tactic\n\n"
            "<describe it: what value is sold, to whom, via which rail, "
            "and which allowlisted tools execute it>\n\n"
            "## Legitimacy check (all must hold)\n\n"
            "- [ ] sells real value; no deception, no spam\n"
            "- [ ] uses only allowlisted tools; no new powers invented\n"
            "- [ ] no fraud, theft, unauthorized access, or market manipulation\n\n"
            "Human: append the approved tactic to tactics/approved.md to activate, "
            "or delete this file.\n"
        )
        path = os.path.join(tactics_dir, f"proposed-{int(time.time())}.md")
        with open(path, "w") as f:
            f.write(draft)
        return f"tactic draft written -> {path} (needs human approval to activate)"


def default_tools() -> list:
    return [
        CheckEarnings(),
        CheckService(),
        SetPrice(),
        PublishListing(),
        Broadcast(),
        SweepFunds(),
        ProposeTactic(),
        Wait(),
        Status(),
    ]
