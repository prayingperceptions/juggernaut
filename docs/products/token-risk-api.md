# Product wiring: Token Risk API

The Juggernaut's first product. A live, pay-per-call token risk intelligence
API ([repo](https://github.com/prayingperceptions/token-risk-api)) — address
in, risk report out, **$0.005 USDC per call** over x402 v2 on Base mainnet.
No signup, no API key.

## The money path

```
agent pays $0.005 USDC (x402)
        │
        ▼
0x2091…5DeA on Base            <- x402 pay-to address
        │
        ▼  (public chain data, direct RPC -- no API key)
bridges/base_rpc_earnings.py  <- eth_getLogs on USDC, converts USDC→sats
        │
        ▼  POST localhost:8787/earn
Juggernaut ledger (sats)       <- epoch survival accounting
        │
        ▼  sweep_funds @ threshold
payouts/payout-*.json          <- instruction for your Coinbase BTC address
```

At ~$86k BTC, one $0.005 call ≈ **6 sats**. The epoch needs ≥1 sat/day, so a
single paying customer per day keeps the Juggernaut alive.

## Setup

**1. Point the hustle at the product.** Copy the example config:

```bash
cp examples/hustle.token-risk.json state/hustle.json
# then set your real payout_address in state/hustle.json
```

This wires `check_service` to `GET /health` on the live API, sets the pitch
the agent advertises, and records the x402 terms.

**2. No API key needed.** The bridge reads Base directly via public RPC.

**3. Run the bridge** next to the Juggernaut:

```bash
python3 bridges/base_rpc_earnings.py \
  --pay-to 0x2091125bFE4259b2CfA889165Beb6290d0Df5DeA \
  --earn-url http://127.0.0.1:8787/earn \
  --source "token-risk-api/x402" \
  --interval 300
```

(The old `bridges/basescan_earnings.py` is kept for paid-plan Etherscan
keys; free-tier keys no longer work for Base since the legacy endpoint
was shut down.)

**4. Run the Juggernaut** (it starts the `POST /earn` webhook itself):

```bash
python run.py --mission missions/sats_or_death.json --brain laya --auto-approve
```

## Honest notes

- **The agent cannot change the x402 price.** `$0.005` is set by `PRICE_USDC`
  in the API's Vercel env. The `price_ladder_sats` in hustle.json is the
  *advertised* ladder the agent experiments with (approval-gated); moving the
  real price means updating the Vercel deployment.
- **Conversion, not custody.** The bridge never touches money — it reads
  public transfers and reports sats-equivalent. USDC stays where it landed
  until you move it.
- **The last mile is still manual in v1.** Sweep instructions go to
  `payouts/`; a human executes the USDC→BTC conversion and the on-chain send
  to the Coinbase address. (Automated path: Alby Hub + Boltz — see
  [payouts.md](../payouts.md).)
- **Demand is the hard part.** The loop is relentless; customers are not
  guaranteed. The agent keeps the service alive, listed, and priced — getting
  agents to actually call it is the real mission, and `propose_tactic` is how
  it opens new fronts.
