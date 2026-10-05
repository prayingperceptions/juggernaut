"""The Juggernaut loop. Relentless, not stupid.

Every tick:
  1. kill switch? -> die
  2. epoch check -> survived | dead | ongoing
  3. brain decides: done? (noul) / next action (choice) / progress (score)
  4. cage checks the action -> act or skip
  5. stall detection -> escalate (notify + wait, never spin forever)

Death writes DEATH_REPORT.md and exits 42. On the next launch, the
lesson from the last death is injected into the brain's state, so each
resurrection starts smarter than the last death.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time

from .wallets import payouts_dir, total_swept

EXIT_DEAD = 42


class Juggernaut:
    def __init__(self, goal, brain, cage, epoch, rail, tools, state_dir, config,
                 save_config, no_sleep=False):
        self.goal = goal
        self.brain = brain
        self.cage = cage
        self.epoch = epoch
        self.rail = rail
        self.tools = {t.name: t for t in tools}
        self.state_dir = state_dir
        self.config = config
        self.save_config = save_config
        self.no_sleep = no_sleep
        os.makedirs(os.path.join(state_dir, "deaths"), exist_ok=True)
        payouts_dir(state_dir)
        os.makedirs(os.path.join(state_dir, "tactics"), exist_ok=True)
        self.tick_log = os.path.join(state_dir, "ticks.jsonl")
        self.lesson = self._load_lesson()
        self._stall_nudge = False
        self._escalation_level = 0

    # -- main loop -----------------------------------------------------
    def run(self):
        print(f"[juggernaut] {self.goal.name}: {self.goal.objective}", flush=True)
        print(f"[juggernaut] rail: {self.rail.describe()}", flush=True)
        tick = 0
        progress_hist = []
        while True:
            tick += 1
            if self.cage.kill_requested():
                return self.die("kill switch engaged (KILL file present)")
            if self.cage.max_ticks and tick > self.cage.max_ticks:
                return self.retire(f"tick budget exhausted ({self.cage.max_ticks})")

            status, info = self.epoch.check()
            if status == "dead":
                return self.die(
                    f"starved: earned {info['earned_sats']} sats in epoch "
                    f"{info['epoch']} (needed {info['needed_sats']})"
                )
            if status == "survived":
                print(f"[juggernaut] SURVIVED epoch {info['epoch'] - 1} -- new epoch begins",
                      flush=True)
                progress_hist = []

            state = self._build_state(tick, info)
            decision = self.brain.decide(state, self.goal, list(self.tools))
            if decision.done_probability >= 0.9:
                return self.win(decision)

            ok, reason = self.cage.check(decision.action)
            if ok:
                result = self.tools[decision.action].run(self._ctx())
                note = f"did {decision.action}: {result}"
            else:
                result, note = "", f"blocked {decision.action}: {reason}"
            print(f"[tick {tick}] {decision.action} "
                  f"(conf {decision.action_confidence:.2f}, progress {decision.progress_label})"
                  f"{' -- ' + note if note else ''}", flush=True)

            self._log_tick(tick, decision, result, note)
            progress_hist.append(decision.progress_index)
            if decision.progress_index > self._escalation_level:
                self._stall_nudge = False  # moving again -- nudge cleared
            if self._stalled(progress_hist):
                self._escalate(tick, progress_hist)

            if not self.no_sleep:
                time.sleep(self.goal.tick_seconds)

    # -- state ---------------------------------------------------------
    def _ctx(self):
        return {
            "goal": self.goal,
            "rail": self.rail,
            "epoch": self.epoch,
            "state_dir": self.state_dir,
            "config": self.config,
            "save_config": self.save_config,
            "recent_ticks": self._recent_ticks,
        }

    def _build_state(self, tick, info):
        recent = self._recent_ticks(5)
        if info.get("survival_clock") == "disabled":
            epoch_line = f"EPOCH: survival clock disabled (one-shot mission)"
        else:
            epoch_line = (
                f"EPOCH: {info['epoch']} | earned {info['earned_sats']} sats "
                f"(need {info['needed_sats']}) | {info['seconds_left']:.0f}s left"
            )
        lines = [
            f"GOAL: {self.goal.objective}",
            f"TICK: {tick}",
            epoch_line,
            f"RAIL: {self.rail.describe()}",
        ]
        if self.lesson:
            lines.append(f"LESSON FROM LAST DEATH: {self.lesson}")
        tactics = self._approved_tactics()
        if tactics:
            lines.append(f"APPROVED TACTICS:\n{tactics}")
        if self._stall_nudge:
            lines.append("YOU ARE STALLED. Consider propose_tactic to open a new front -- "
                         "never accept a market 'no' as final.")
        lines.append(f"PAYOUT: {self._payout_status()}")
        if recent:
            lines.append("RECENT TICKS:")
            lines.extend(f"  - {r}" for r in recent)
        return "\n".join(lines)

    def _recent_ticks(self, n):
        if not os.path.exists(self.tick_log):
            return []
        with open(self.tick_log) as f:
            lines = f.readlines()[-n:]
        out = []
        for line in lines:
            try:
                t = json.loads(line)
                out.append(f"t{t['tick']} {t['action']}: {t['note'][:100]}")
            except (json.JSONDecodeError, KeyError):
                continue
        return out

    def _log_tick(self, tick, decision, result, note):
        with open(self.tick_log, "a") as f:
            f.write(json.dumps({
                "tick": tick,
                "ts": time.time(),
                "action": decision.action,
                "confidence": round(decision.action_confidence, 3),
                "progress": decision.progress_label,
                "result": str(result)[:300],
                "note": note[:300],
            }) + "\n")

    def _stalled(self, hist):
        n = self.goal.stall_ticks
        return len(hist) >= n and max(hist[-n:]) <= hist[-n]

    def _escalate(self, tick, hist):
        self._stall_nudge = True
        self._escalation_level = hist[-1]
        msg = (f"progress stalled for {self.goal.stall_ticks} ticks "
               f"(level {hist[-1]}). Requesting human guidance -- holding pattern.")
        print(f"[juggernaut] ESCALATION at tick {tick}: {msg}", flush=True)
        with open(os.path.join(self.state_dir, "ESCALATION.md"), "w") as f:
            f.write(f"# Escalation (tick {tick})\n\n{msg}\n")

    def _approved_tactics(self) -> str:
        p = os.path.join(self.state_dir, "tactics", "approved.md")
        if os.path.exists(p):
            with open(p) as f:
                return f.read()[:2000]
        return ""

    def _payout_status(self) -> str:
        cfg = self.config
        addr = str(cfg.get("payout_address", "")).strip()
        if not addr:
            return "no payout address configured (set payout_address in hustle.json)"
        earned = self.rail.sats_earned_since(0)
        swept = total_swept(self.state_dir)
        return (f"payout_address ...{addr[-6:]}, earned_total={earned}, swept={swept}, "
                f"sweepable={earned - swept}, "
                f"threshold={cfg.get('sweep_threshold_sats', 1000)}, "
                f"mode={cfg.get('sweep_mode', 'manual')}")

    # -- endings -------------------------------------------------------
    def _load_lesson(self):
        report = os.path.join(self.state_dir, "DEATH_REPORT.md")
        if not os.path.exists(report):
            return ""
        with open(report) as f:
            text = f.read()
        # archive it; the lesson lives on in state
        stamp = time.strftime("%Y%m%d-%H%M%S")
        shutil.move(report, os.path.join(self.state_dir, "deaths", f"death-{stamp}.md"))
        lesson = ""
        for line in text.splitlines():
            if line.startswith("Lesson:"):
                lesson = line[len("Lesson:"):].strip()
        return lesson or "I died last run. Do not repeat the same pattern."

    def die(self, reason):
        _, info = self.epoch.check()
        recent = self._recent_ticks(20)
        report = (
            f"# DEATH REPORT -- {self.goal.name}\n\n"
            f"Died: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Reason: {reason}\n\n"
            f"## Final epoch\n\n"
            f"- Epoch: {info.get('epoch')}\n"
            f"- Earned: {info.get('earned_sats', 'n/a')} sats "
            f"(needed {info.get('needed_sats', 'n/a')})\n"
            f"- Rail: {self.rail.describe()}\n\n"
            f"## Last actions\n\n" +
            "".join(f"- {r}\n" for r in recent) +
            f"\nLesson: <write what to do differently next run>\n"
        )
        with open(os.path.join(self.state_dir, "DEATH_REPORT.md"), "w") as f:
            f.write(report)
        self.epoch.reset()  # resurrection begins a fresh epoch, not the failed one
        print(f"\n[juggernaut] DIED: {reason}", flush=True)
        print("[juggernaut] death report written. Resurrect me smarter.", flush=True)
        sys.exit(EXIT_DEAD)

    def retire(self, reason):
        print(f"\n[juggernaut] RETIRED: {reason}", flush=True)
        sys.exit(0)

    def win(self, decision):
        print(f"\n[juggernaut] GOAL ACCOMPLISHED "
              f"(P={decision.done_probability:.2f}). The Juggernaut rests.", flush=True)
        sys.exit(0)
