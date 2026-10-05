# Payouts (operator reference)

Sweep rule in `state/hustle.json` (user-configured, never agent-configured):

- `payout_address` — always ask the user. Never invent.
- `sweep_threshold_sats` — sweep when sweepable ≥ this.
- `sweep_mode` — `manual` (default): instruction written to `payouts/`, human
  executes, flips status to `"done"`. `auto`: pre-authorized, cage waives
  per-payout approval (v1 still writes the instruction; no auto backend ships).

Sweep accounting counts pending + done: sats are never swept twice.

Live earnings webhook (localhost only):

```bash
curl -X POST localhost:8787/earn -H 'Content-Type: application/json' \
  -d '{"sats": 500, "source": "alby-hub", "tx": "abc123"}'
```

Full automation path (document, don't improvise): Alby Hub via Nostr Wallet
Connect for Lightning, Boltz submarine swaps for Lightning → on-chain BTC.
Keep `manual` until small amounts prove the backend.
