# Architecture

```
mission JSON ──> Goal ──┐
                        │
  ┌─────────────────────┴──────────────────────┐
  │                  JUGGERNAUT LOOP           │
  │                                            │
  │   tick ──> BRAIN (laya-mlx, ~30ms)         │
  │     ├─ done?      (noul: P(accomplished))  │
  │     ├─ next move? (choice over tools)      │
  │     └─ progress?  (score over rubric)      │
  │              │                             │
  │              v                             │
  │            CAGE ── allowlist / approvals / │
  │              │      kill switch            │
  │              v                             │
  │            TOOL ──> world                  │
  │              │                             │
  │   stall? ──> escalate + propose tactic     │
  │                                            │
  │   epoch ended?                             │
  │     ├─ earned >= min ──> SURVIVE, new epoch│
  │     └─ earned < min  ──> DIE (exit 42)     │
  └────────────────────────────────────────────┘
         │                        │
    ticks.jsonl              DEATH_REPORT.md ──> lesson ──> next run
    ledger.jsonl             payouts/
```

## Components

| File | Role |
|---|---|
| `juggernaut/goal.py` | The single goal. Typed, loaded from mission JSON. |
| `juggernaut/brain.py` | Reflex layer. `LayaBrain` (laya-mlx, Apple Silicon) or `FakeBrain` (testing). |
| `juggernaut/cage.py` | Allowlist, approvals, kill switch. Checked every tick. |
| `juggernaut/epochs.py` | Survival clock. Persists on disk; reboots don't reset it. |
| `juggernaut/agent.py` | The loop: decide → cage → act → log → epoch check. |
| `juggernaut/tools.py` | The hustle toolbox. The only powers the agent has. |
| `juggernaut/wallets.py` | Payout instructions + sweep accounting. |
| `juggernaut/rails/` | Earnings rails: `ledger` (live webhook) / `simulator` (dry-run). |
| `juggernaut/cli.py` | CLI wiring. |

## Key design decisions

**The brain only picks action names.** Laya answers typed questions; it never
writes code, never touches keys, never invents powers. New capability requires
a human writing a tool — creativity in *sequencing*, not in *privilege*.

**Epochs persist.** `epoch.json` survives restarts. The agent cannot cheat
death by rebooting.

**Death is a feature.** Exit 42 + `DEATH_REPORT.md`. Resurrection injects the
last lesson into the brain's state. Failed runs compound into smarter runs.

**Stall ≠ death.** No progress for `stall_ticks` → escalation + a nudge to
`propose_tactic`. Relentless, not stupid: it opens new fronts instead of
spinning.

**Sweep accounting is append-only.** `total_swept` counts pending + done
instructions, so the same sats are never swept twice.
