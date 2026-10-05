<div align="center">

# JUGGERNAUT

**A template for relentless, single-goal AI agents. One goal, or die.**

[![MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)](.github/workflows/ci.yml)

*Give it one mission. It does not quit, it does not get distracted, it does not
accept "no" from the world. It earns, or it dies — and every death makes the
next run smarter.*

[Doctrine](docs/doctrine.md) · [Missions](docs/missions.md) · [Architecture](docs/architecture.md) · [Payouts](docs/payouts.md)

</div>

---

Juggernaut is a template for building AI agents that accept exactly one
mission and pursue it until completion. Its reflex layer is
[laya-mlx](https://pypi.org/project/laya-mlx/) — an open-weight decision
engine that answers *done?*, *what next?*, and *how am I doing?* in a single
~10ms forward pass, fully local on Apple Silicon. A survival clock enforces
the mission: earn or accomplish within each epoch, or die — writing a death
report that makes the next run smarter. Market "no"s are never final; the
cage (allowlists, approvals, kill switch) is absolute. Its first mission,
SATS OR DEATH, earns Bitcoin daily via a live x402 pay-per-call API on Base.

## The idea

Most agents are interns: they try, they stall, they ask what you meant. A
**Juggernaut** is the opposite. It holds exactly one goal and pursues it with
everything it has until the goal is complete — or until its survival clock
runs out, at which point it dies, writes up what killed it, and comes back
smarter.

The trick that makes "relentless" affordable: the reflex layer is
**[laya-mlx](https://pypi.org/project/laya-mlx/)**, an open-weight typed-decision
engine. Every tick the agent asks three constrained questions — *am I done?*
(True/False), *what's my next move?* (pick one tool), *am I getting closer?*
(score 0–4) — in **~30ms total, fully local, zero output tokens, zero API
cost**. An LLM loop lumbers at seconds and cents per tick. The Juggernaut
ticks thousands of times an hour for free.

## The doctrine

Two kinds of "no":

- **"No" from the world** (no buyers, service down, tactic failed) — never
  final. Retry, reprice, relist, propose a new tactic, charge again. Forever.
- **"No" from the cage** (allowlist, approvals, kill switch) — absolute.
  Ruthless inside the cage; the cage is not negotiable.

And "whatever it takes" has a boundary: **legitimate means only**. Fraud,
spam, and theft aren't tactics — they're mission-killers. Full doctrine:
[docs/doctrine.md](docs/doctrine.md).

## Quickstart

```bash
pip install juggernaut-agent
```

Watch it starve and die (fake brain, scripted earnings, nothing real):

```bash
juggernaut --mission missions/sats_or_death.json --dry-run --ticks 40 --epoch-minutes 0.2
# ... ticks ...
# [juggernaut] DIED: starved: earned 0 sats in epoch 1 (needed 1)
# [juggernaut] death report written. Resurrect me smarter.
```

Watch it survive:

```bash
juggernaut --mission missions/sats_or_death.json --dry-run --sim-pays --epoch-minutes 0.2
```

Go live (Mac, Apple Silicon):

```bash
pip install "juggernaut-agent[brain]"
juggernaut --mission missions/sats_or_death.json --auto-approve
```

Kill it anytime: `touch state/KILL`

## Mission 1: SATS OR DEATH

Make Bitcoin every single day, or die. Each 24-hour epoch must see net-new
sats land from external sources; earnings forward to your payout address per
your sweep rule. Zero-earning epoch → exit 42 + `DEATH_REPORT.md`. Relaunch →
the lesson injects into the brain. Evolutionary pressure, on purpose.

Record live earnings from anything with a webhook:

```bash
curl -X POST localhost:8787/earn -H 'Content-Type: application/json' \
  -d '{"sats": 500, "source": "alby-hub", "tx": "abc123"}'
```

## How it works

```
mission JSON → GOAL → ┌─────────────────────────────┐
                      │  TICK                       │
                      │   brain: done? move? closer?│  (~30ms, laya-mlx)
                      │   cage:  allowlist/approvals│
                      │   tool:  act on the world    │
                      │  STALL? → escalate + new tactic
                      │  EPOCH? → survive | DIE (42) │
                      └─────────────────────────────┘
```

- **Brain** only picks tool names. It can't invent powers, touch keys, or move funds.
- **Cage** is checked every tick. Approval-gated actions (`set_price`, `broadcast`, `sweep_funds`) need a human unless pre-authorized.
- **Epochs persist** — rebooting doesn't reset the clock. No cheating death.
- **Stall ≠ death** — flat progress triggers escalation and a nudge to propose a new tactic, not a spin loop.

Details: [docs/architecture.md](docs/architecture.md)

## Write your own mission

```json
{
  "name": "REFUND HOUND",
  "objective": "Recover the $47.13 duplicate charge from Acme Corp.",
  "done_proposition": "The $47.13 duplicate charge has been refunded.",
  "progress_rubric": ["no contact", "ticket filed", "escalated", "promised", "refunded"],
  "epoch_hours": 0,
  "tick_seconds": 300
}
```

```bash
juggernaut --mission my_mission.json --dry-run
```

New powers = new tools in `juggernaut/tools.py` (automatically allowlisted and
cage-bound). Guide: [docs/missions.md](docs/missions.md)

## FAQ

**Is this safe to run?**
The agent cannot move funds, spend, or exfiltrate keys — no such tool exists.
Outward/irreversible actions need your approval. `touch state/KILL` stops it
cold. Read [docs/doctrine.md](docs/doctrine.md).

**Why not just use an LLM agent loop?**
Cost and speed. A Juggernaut tick is three typed decisions in ~30ms for $0.
An LLM tick is seconds and cents. Relentlessness is a budget problem first —
Laya solves it.

**Does it need the Mac?**
Only the real brain (`laya-mlx` is Apple Silicon). The loop, cage, epochs,
and dry-runs work anywhere Python 3.11+ runs.

**Can it actually earn Bitcoin?**
It can hustle: keep a paid service alive, visible, and well-priced, and watch
the money. It can't print money — anyone promising that is selling something.
The first live epoch will probably kill it. Read the death report, improve the
hustle, resurrect.

## Contributing

PRs welcome. The doctrine is load-bearing: no PR may grant the agent a power
that bypasses the cage. Run `pytest -q` before pushing.

---

<div align="center">

*One goal. No distractions. No surrender.*

⭐ If the Juggernaut survives its first epoch, star the repo.

</div>
