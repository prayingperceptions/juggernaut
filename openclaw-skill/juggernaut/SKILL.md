---
name: juggernaut
description: Run a JUGGERNAUT — a relentless single-goal agent that pursues ONE mission without quitting, stalling, or getting distracted, and dies (with a death report) if it fails its survival clock. USE WHEN the user wants an agent that will not take no for an answer: earn bitcoin every day (SATS OR DEATH), chase a refund until it lands, stalk a deal until the price hits, grind any single objective to completion. Trigger phrases: "juggernaut", "relentless agent", "single-goal agent", "never give up", "don't stop until", "earn bitcoin", "or die", "like Jason Bourne", "hyperfocused agent". NOT FOR: casual Q&A, one-shot tasks you can do directly, anything asking the agent to break the law, deceive, steal, spam, or bypass safety constraints — the cage is absolute.
---

# Juggernaut

A Juggernaut holds **exactly one goal** and pursues it relentlessly: decide →
act → check → repeat, thousands of ticks, until done or dead. Its reflex layer
is laya-mlx (typed decisions in ~30ms, local, free). You are the operator: you
write the mission, set the cage, and resurrect it smarter after each death.

## Invoke

```
# Dry run first — always. Fake brain, scripted earnings, nothing real.
juggernaut --mission missions/sats_or_death.json --dry-run --ticks 40 --epoch-minutes 0.2

# Live run (needs Apple Silicon for the laya-mlx brain)
juggernaut --mission missions/my_mission.json --auto-approve

# Stop it cold
touch state/KILL
```

## Steps

### 1. Write the mission (with the user)

A mission is JSON (`missions/_template.json`). Help the user write:

- `objective` — ONE sentence, no conjunctions. The only thing that matters.
- `done_proposition` — the True/False question. P ≥ 0.9 wins the run.
- `progress_rubric` — 3–6 ordered, observable levels (stall detection needs signal).
- `epoch_hours` / `min_sats_per_epoch` — survival clock, or `0`/`0` to disable for one-shot missions.
- `tick_seconds`, `stall_ticks`, `max_ticks` — pacing and guardrails.

See `references/missions.md`.

### 2. Configure the hustle

`state/hustle.json` (created on first run): `service_url`, `pitch`,
`price_ladder_sats`, plus the payout rule — `payout_address`,
`sweep_threshold_sats`, `sweep_mode` (`manual` default). Never invent a payout
address; always ask the user.

### 3. Dry-run before live

Always `--dry-run` first. Show the user the tick log. Confirm the brain cycles
tools sanely and the cage blocks approval-gated actions.

### 4. Go live, then operate the lifecycle

- **Ticks**: watch `ticks.jsonl`. Progress flat for `stall_ticks` → the agent
  escalates and drafts a tactic in `tactics/proposed-*.md`.
- **Tactics**: review drafts with the user. Approved ones go in
  `tactics/approved.md` — they inject into the brain's state next run.
- **Death**: exit 42 + `DEATH_REPORT.md`. Read it with the user, fill the
  `Lesson:` line, relaunch. Each resurrection starts smarter.
- **Payouts**: `sweep_funds` writes instructions to `payouts/`. In `manual`
  mode the user executes them. See `references/payouts.md`.

### 5. New powers = new tools (with the user)

Tools live in `juggernaut/tools.py` and are the ONLY powers the agent has.
Propose tools; the user approves. Never add a tool that moves funds, spends,
exfiltrates keys, spams, or deceives — and never bypass the cage to "make it
work".

## Rules

- One goal per mission. If the user adds a second goal, that's a second mission.
- "No" from the world is never final (retry, adapt). "No" from the cage is
  absolute (allowlist, approvals, kill switch). See `references/doctrine.md`.
- Legitimate means only. If a proposed tactic involves fraud, theft, spam,
  deception, or unauthorized access: refuse that tactic, explain why, propose a
  legitimate alternative.
- `--auto-approve` and `sweep_mode: auto` are the user's call, never yours to
  set silently. Default to approvals on.
- The agent's brain only picks tool names — it cannot invent capabilities.
  Keep it that way.

## Script

The skill's backing CLI (installed via `pip install juggernaut-agent`):

```bash
juggernaut --mission <mission.json> [--dry-run] [--auto-approve] [--state-dir state]
python3 {baseDir}/scripts/doctor.py   # pre-flight checks
```
