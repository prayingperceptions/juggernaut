#!/usr/bin/env python3
"""Bridge: x402 USDC earnings -> Juggernaut sats (keyless, direct RPC).

Reads Base chain data straight from a public RPC endpoint with
eth_getLogs -- no indexer, no API key, nothing to revoke. Watches the
USDC contract for Transfer events into a product's x402 pay-to address,
converts each to sats at the live BTC price, and POSTs to the
Juggernaut's earnings webhook. Pure public data -- no keys to the money.

Run alongside the Juggernaut (example: Token Risk API):
    python3 bridges/base_rpc_earnings.py \\
        --pay-to 0x2091125bFE4259b2CfA889165Beb6290d0Df5DeA \\
        --earn-url http://127.0.0.1:8787/earn \\
        --source "token-risk-api/x402" \\
        --interval 300

Optional: --rpc-url to use your own Base RPC (Alchemy, etc.) instead of
the public endpoint. Stdlib only. Polls every --interval seconds, forever.

Why this exists: the Basescan legacy API endpoint was shut down and the
unified Etherscan V2 API no longer serves Base on free-tier keys
("Free API access is not supported for this chain"). Direct RPC reads
need no key at all.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

# allow `python3 bridges/base_rpc_earnings.py` from the repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridges.basescan_earnings import btc_usd_price, post_earn, usdc_to_sats

USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # real Base USDC
# keccak256("Transfer(address,address,uint256)") -- the ERC-20 Transfer event
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
DEFAULT_RPC = "https://mainnet.base.org"
MAX_SEEN = 5000


# -- pure logic (testable without network) -------------------------------

def pad_topic_address(addr: str) -> str:
    """Left-pad an address to a 32-byte log topic."""
    a = addr.lower()
    if a.startswith("0x"):
        a = a[2:]
    if len(a) != 40 or any(c not in "0123456789abcdef" for c in a):
        raise ValueError(f"not an EVM address: {addr}")
    return "0x" + a.rjust(64, "0")


def parse_transfer_log(log: dict) -> dict | None:
    """Extract tx hash + raw USDC base-units + block from an eth_getLogs entry."""
    try:
        return {
            "hash": log["transactionHash"],
            "value": int(log["data"], 16),  # USDC: 6 decimals
            "block": int(log["blockNumber"], 16),
        }
    except (KeyError, ValueError, TypeError, AttributeError):
        return None


def build_log_filter(pay_to: str, from_block: int, to_block: int) -> dict:
    """eth_getLogs filter: USDC Transfer events *into* pay_to."""
    return {
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block),
        "address": USDC_BASE,
        "topics": [TRANSFER_TOPIC, None, pad_topic_address(pay_to)],
    }


# -- network ---------------------------------------------------------------

def _rpc(rpc_url: str, method: str, params: list, timeout: int = 25):
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    ).encode()
    req = urllib.request.Request(
        rpc_url, data=body,
        headers={"Content-Type": "application/json",
                 "User-Agent": "juggernaut-bridge/0.2"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(f"rpc error: {data['error']}")
    return data["result"]


def head_block(rpc_url: str) -> int:
    return int(_rpc(rpc_url, "eth_blockNumber", []), 16)


def fetch_logs(rpc_url: str, pay_to: str, from_block: int, to_block: int) -> list:
    return _rpc(rpc_url, "eth_getLogs",
                [build_log_filter(pay_to, from_block, to_block)])


# Public RPCs (e.g. mainnet.base.org) reject eth_getLogs over wide block
# ranges with HTTP 413. Chunk the scan so a long catch-up never fails as
# one giant request -- and, critically, never gets stuck: without chunking,
# a 413 leaves last_block unadvanced and every later poll 413s the same way.
MAX_RANGE_BLOCKS = 500


def fetch_logs_chunked(rpc_url: str, pay_to: str,
                       from_block: int, to_block: int) -> list:
    """eth_getLogs over [from_block, to_block], in MAX_RANGE_BLOCKS chunks."""
    out: list = []
    cur = from_block
    while cur <= to_block:
        chunk_end = min(cur + MAX_RANGE_BLOCKS - 1, to_block)
        out.extend(fetch_logs(rpc_url, pay_to, cur, chunk_end))
        cur = chunk_end + 1
    return out


# -- state -------------------------------------------------------------------

def load_state(path: str) -> tuple[int | None, set]:
    if os.path.exists(path):
        try:
            with open(path) as f:
                d = json.load(f)
            return d.get("last_block"), set(d.get("seen", []))
        except (json.JSONDecodeError, AttributeError):
            pass
    return None, set()


def save_state(path: str, last_block: int | None, seen: set) -> None:
    seen = set(list(seen)[-MAX_SEEN:])
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"last_block": last_block, "seen": sorted(seen)}, f)
    os.replace(tmp, path)


# -- main loop -----------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Bridge x402 USDC earnings to Juggernaut sats via direct Base RPC.")
    ap.add_argument("--pay-to", required=True, help="x402 receiving address on Base")
    ap.add_argument("--earn-url", default="http://127.0.0.1:8787/earn")
    ap.add_argument("--source", default="x402", help="source label for the ledger")
    ap.add_argument("--rpc-url", default=DEFAULT_RPC, help="Base JSON-RPC endpoint")
    ap.add_argument("--interval", type=int, default=300, help="poll seconds")
    ap.add_argument("--confirmations", type=int, default=5,
                    help="blocks to lag behind head (reorg safety)")
    ap.add_argument("--backfill", type=int, default=600,
                    help="blocks to scan back on first run (~2s/block on Base)")
    ap.add_argument("--state", default="state/bridge_base_rpc.json")
    ap.add_argument("--once", action="store_true", help="single poll, then exit")
    args = ap.parse_args()

    last_block, seen = load_state(args.state)
    print(f"[bridge] watching USDC -> {args.pay_to} via {args.rpc_url} "
          f"| earn -> {args.earn_url} | {len(seen)} seen", flush=True)

    while True:
        try:
            head = head_block(args.rpc_url)
            tip = head - args.confirmations
            if last_block is None:
                last_block = tip - args.backfill
                print(f"[bridge] first run: backfilling from block {last_block}",
                      flush=True)
            if tip <= last_block:
                print(f"[bridge] caught up at block {last_block}", flush=True)
            else:
                logs = fetch_logs_chunked(args.rpc_url, args.pay_to,
                                          last_block + 1, tip)
                price = btc_usd_price()
                fresh = 0
                failed_blocks = []
                for log in logs:
                    parsed = parse_transfer_log(log)
                    if not parsed or parsed["hash"] in seen:
                        continue
                    usdc = parsed["value"] / 1e6
                    if usdc <= 0:
                        continue
                    sats = usdc_to_sats(usdc, price)
                    if sats <= 0:
                        continue  # dust: below 1 sat, not worth ledgering
                    try:
                        post_earn(args.earn_url, sats, args.source, parsed["hash"])
                    except Exception as e:
                        # don't mark seen: retry next poll, no double-count
                        print(f"[bridge] earn post failed for "
                              f"{parsed['hash'][:10]}...: {e}", flush=True)
                        failed_blocks.append(parsed["block"])
                        continue
                    seen.add(parsed["hash"])
                    save_state(args.state, last_block, seen)  # crash-safe
                    fresh += 1
                    print(f"[bridge] +{sats} sats from {parsed['hash'][:10]}... "
                          f"(BTC ${price:,.0f})", flush=True)
                # never advance past a block whose earnings failed to record;
                # it gets re-scanned next poll (seen-set dedups the rest)
                last_block = min([tip] + [b - 1 for b in failed_blocks])
                save_state(args.state, last_block, seen)
                if not fresh:
                    print(f"[bridge] no new earnings through block {tip} "
                          f"(BTC ${price:,.0f})", flush=True)
        except Exception as e:  # never die on a bad poll; retry next interval
            print(f"[bridge] poll failed: {e}", flush=True)
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
