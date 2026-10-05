# Missions (operator reference)

Copy `missions/_template.json`. Fields:

- `name` — shouted in logs.
- `objective` — one sentence, no conjunctions. The only thing that matters.
- `done_proposition` — True/False question; P ≥ 0.9 wins.
- `progress_rubric` — 3–6 ordered, observable levels.
- `epoch_hours` / `min_sats_per_epoch` — survival clock; `0`/`0` disables it.
- `tick_seconds`, `stall_ticks`, `max_ticks` — pacing and guardrails.

Good objectives are observable: "Recover the $47.13 duplicate charge" beats
"achieve justice". Rubric levels must map to visible milestones or stall
detection has no signal.

Example missions: `missions/sats_or_death.json` (survival),
`examples/refund_hound.json` (one-shot).
