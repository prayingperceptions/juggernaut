# Payouts

The agent earns; you decide where it goes. The sweep rule lives in
`state/hustle.json` and is set by the **user**, never the agent.

```json
{
  "payout_address": "bc1q...",
  "sweep_threshold_sats": 1000,
  "sweep_mode": "manual"
}
```

## How it works

1. Every tick, the brain sees sweepable = earned_total − already_swept.
2. When sweepable ≥ threshold, `sweep_funds` writes a payout instruction to
   `payouts/payout-<ts>.json` with `status: "pending"`.
3. Sweep accounting counts pending + done, so sats are never swept twice.

## Modes

| Mode | Behavior |
|---|---|
| `manual` (default) | Instruction is written; a human executes it, flips `status` to `"done"`. The agent never touches keys. |
| `auto` | The sweep rule is pre-authorized: the cage waives per-payout approval. v1 still writes the instruction (no auto backend ships); a backend implements `PayoutBackend.send()` to broadcast. |

## Automating payouts (advanced)

v1 deliberately ships no automated money-movement backend. The interface is
ready (`juggernaut/wallets.py::PayoutBackend`). The documented path:

1. **Lightning receive:** Alby Hub (self-hosted) exposes Nostr Wallet Connect —
   the agent holds an NWC connection string, never seed words.
2. **Lightning → on-chain BTC:** Boltz submarine swaps
   (`POST /v1/createswap`, Lightning in → BTC out to your address).
3. Keep `sweep_mode: manual` until the backend has proven itself on small
   amounts. Then flip to `auto`.

## Recording live earnings

Point any webhook at the ledger rail:

```bash
curl -X POST localhost:8787/earn -H 'Content-Type: application/json' \
  -d '{"sats": 500, "source": "alby-hub", "tx": "abc123"}'
```

Alby Hub, LNbits, Strike, or your own paid API posting every settled call.
Only localhost can post. Only positive integers are accepted.
