#!/usr/bin/env python3
"""Bridge: x402 USDC earnings -> Juggernaut sats.

Polls Basescan for USDC transfers to a product's x402 pay-to address on
Base, converts each to sats at the live BTC price, and POSTs to the
Juggernaut's earnings webhook. Pure public data -- no keys to the money.

Needs: BASESCAN_API_KEY env var (free at https://basescan.org/myapikey)

NOTE (2026-10): the legacy api.basescan.org endpoint was shut down and the
unified Etherscan V2 API no longer serves Base on free-tier keys. Prefer
bridges/base_rpc_earnings.py, which needs no key at all. This module is
kept for paid-plan keys and as the home of the shared conversion helpers.

Run alongside the Juggernaut (example: Token Risk API):
    BASESCAN_API_KEY=xxx python3 bridges/basescan_earnings.py \\
        --pay-to 0x2091125bFE4259b2CfA889165Beb6290d0Df5DeA \\
        --earn-url http://127.0.0.1:8787/earn \\
        --source "token-risk-api/x402" \\
        --interval 300

Stdlib only. Polls every --interval seconds, forever.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # real Base USDC
BASESCAN_API = "https://api.basescan.org/api"
COINBASE_SPOT = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
MAX_SEEN = 5000


# -- pure logic (testable without network) -------------------------------

def usdc_to_sats(usdc: float, btc_usd: float) -> int:
    """Convert a USDC amount to sats at the given BTC price."""
    if btc_usd <= 0:
        raise ValueError("btc_usd must be positive")
    return int(usdc / btc_usd * 1e8)


def new_earnings(transfers: list, pay_to: str, seen_hashes: set,
                 btc_usd: float) -> list:
    """Filter raw Basescan transfers down to new, payable earnings.

    Returns [{"hash":..., "sats":..., "ts":...}] for USDC transfers into
    pay_to that we haven't seen before.
    """
    pay_to = pay_to.lower()
    out = []
    for t in transfers:
        try:
            h = t["hash"]
            if h in seen_hashes:
                continue
            if t.get("to", "").lower() != pay_to:
                continue
            if t.get("tokenSymbol") != "USDC":
                continue
            usdc = int(t.get("value", "0")) / 1e6
            if usdc <= 0:
                continue
            sats = usdc_to_sats(usdc, btc_usd)
            if sats <= 0:
                continue
            out.append({"hash": h, "sats": sats, "ts": int(t.get("timeStamp", 0))})
        except (KeyError, ValueError, TypeError):
            continue
    return out


# -- network ---------------------------------------------------------------

def _get_json(url: str, timeout: int = 20) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "juggernaut-bridge/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def btc_usd_price() -> float:
    data = _get_json(COINBASE_SPOT)
    return float(data["data"]["amount"])


def fetch_transfers(api_key: str, pay_to: str) -> list:
    url = (f"{BASESCAN_API}?module=account&action=tokentx"
           f"&contractaddress={USDC_BASE}&address={pay_to}"
           f"&page=1&offset=100&sort=desc&apikey={api_key}")
    data = _get_json(url)
    if isinstance(data, dict) and data.get("status") == "1":
        return data.get("result", [])
    msg = data.get("message", "unknown") if isinstance(data, dict) else "bad response"
    raise RuntimeError(f"basescan error: {msg}")


def post_earn(earn_url: str, sats: int, source: str, tx: str) -> None:
    body = json.dumps({"sats": sats, "source": source, "tx": tx}).encode()
    req = urllib.request.Request(earn_url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        if r.status != 200:
            raise RuntimeError(f"earn webhook returned {r.status}")


# -- state -------------------------------------------------------------------

def load_state(path: str) -> set:
    if os.path.exists(path):
        try:
            with open(path) as f:
                return set(json.load(f).get("seen", []))
        except (json.JSONDecodeError, AttributeError):
            pass
    return set()


def save_state(path: str, seen: set) -> None:
    seen = set(list(seen)[-MAX_SEEN:])
    with open(path, "w") as f:
        json.dump({"seen": sorted(seen)}, f)


# -- main loop -----------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Bridge x402 USDC earnings to Juggernaut sats.")
    ap.add_argument("--pay-to", required=True, help="x402 receiving address on Base")
    ap.add_argument("--earn-url", default="http://127.0.0.1:8787/earn")
    ap.add_argument("--source", default="x402", help="source label for the ledger")
    ap.add_argument("--interval", type=int, default=300, help="poll seconds")
    ap.add_argument("--state", default="state/bridges/basescan_state.json")
    ap.add_argument("--once", action="store_true", help="single poll, then exit")
    args = ap.parse_args()

    api_key = os.environ.get("BASESCAN_API_KEY", "").strip()
    if not api_key:
        print("error: set BASESCAN_API_KEY env var (free at https://basescan.org/myapikey)",
              file=sys.stderr)
        sys.exit(2)

    seen = load_state(args.state)
    print(f"[bridge] watching USDC -> {args.pay_to} | earn -> {args.earn_url} "
          f"| {len(seen)} seen", flush=True)
    while True:
        try:
            price = btc_usd_price()
            transfers = fetch_transfers(api_key, args.pay_to)
            fresh = new_earnings(transfers, args.pay_to, seen, price)
            for e in sorted(fresh, key=lambda x: x["ts"]):
                post_earn(args.earn_url, e["sats"], args.source, e["hash"])
                seen.add(e["hash"])
                print(f"[bridge] +{e['sats']} sats from {e['hash'][:10]}... "
                      f"(BTC ${price:,.0f})", flush=True)
            if fresh:
                save_state(args.state, seen)
            else:
                print(f"[bridge] no new earnings (BTC ${price:,.0f})", flush=True)
        except Exception as e:  # never die on a bad poll; retry next interval
            print(f"[bridge] poll failed: {e}", flush=True)
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
