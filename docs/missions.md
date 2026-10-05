# Writing Missions

A mission is a JSON file. Copy `missions/_template.json`.

```json
{
  "name": "REFUND HOUND",
  "objective": "Recover the $47.13 duplicate charge from Acme Corp. Nothing else matters until the refund lands.",
  "done_proposition": "The $47.13 duplicate charge has been refunded.",
  "progress_rubric": ["no contact", "ticket filed", "escalated", "promised", "refunded"],
  "epoch_hours": 0,
  "min_sats_per_epoch": 0,
  "tick_seconds": 300,
  "stall_ticks": 12,
  "max_ticks": 0
}
```

## Fields

| Field | Meaning |
|---|---|
| `name` | Mission name, shouted in logs. |
| `objective` | One sentence. The only thing that matters. |
| `done_proposition` | The `noul` question. P ≥ 0.9 wins the run. |
| `progress_rubric` | Ordered levels for the `score` question. 3–6 levels. |
| `epoch_hours` | Survival window. `0` disables the clock (one-shot missions). |
| `min_sats_per_epoch` | Earnings needed per epoch, or die. `0` with `epoch_hours: 0`. |
| `tick_seconds` | Seconds between ticks. |
| `stall_ticks` | Ticks without progress before escalation. |
| `max_ticks` | Hard stop. `0` = unlimited. |

## Writing good objectives

- **One goal, no conjunctions.** "Recover the refund" beats "recover the refund and find a better vendor".
- **Observable done.** The `done_proposition` must be checkable from state text. "Refund landed" > "justice served".
- **Rubric mirrors reality.** Levels should map to visible milestones, so the stall detector has signal.

## Mission ideas

- `sats_or_death.json` — make Bitcoin every day or die (included).
- Refund hound — chase one charge until it's reversed.
- Deal stalker — watch one route/fare until it beats your threshold, then alert.
- Inbox zero — every inbound message triaged until the queue is empty.
- Grant hunter — one RFP pursued through every draft until submitted.
