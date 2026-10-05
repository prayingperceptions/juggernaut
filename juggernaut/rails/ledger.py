"""Ledger rail: append-only earnings ledger + local webhook.

The live rail. Any external system records earnings by appending to
ledger.jsonl or POSTing to the local webhook:

    curl -X POST localhost:8787/earn \\
      -H 'Content-Type: application/json' \\
      -d '{"sats": 500, "source": "alby-hub", "tx": "abc123"}'

Wire your Lightning webhooks here (Alby Hub, LNbits, Strike...), or have
your paid API post every settled x402 call. Only localhost can post.
"""
from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import EarningsRail


class LedgerRail(EarningsRail):
    def __init__(self, state_dir: str, port: int = 8787):
        self.state_dir = state_dir
        self.ledger_path = os.path.join(state_dir, "ledger.jsonl")
        os.makedirs(state_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._server = None
        if port:
            self._serve(port)

    # -- recording -----------------------------------------------------
    def record(self, sats: int, source: str, tx: str = "") -> dict:
        if not isinstance(sats, int) or sats <= 0:
            raise ValueError("sats must be a positive integer")
        entry = {
            "ts": time.time(),
            "sats": sats,
            "source": str(source)[:120],
            "tx": str(tx)[:160],
        }
        with self._lock:
            with open(self.ledger_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        return entry

    def sats_earned_since(self, since_ts: float) -> int:
        total = 0
        if not os.path.exists(self.ledger_path):
            return 0
        with self._lock:
            with open(self.ledger_path) as f:
                for line in f:
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if e.get("ts", 0) >= since_ts:
                        total += int(e.get("sats", 0))
        return total

    def describe(self) -> str:
        return f"LedgerRail({self.ledger_path})"

    # -- webhook -------------------------------------------------------
    def _serve(self, port: int):
        rail = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != "/earn":
                    self.send_response(404)
                    self.end_headers()
                    return
                length = int(self.headers.get("Content-Length", 0))
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                    entry = rail.record(
                        int(body["sats"]),
                        body.get("source", "unknown"),
                        body.get("tx", ""),
                    )
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "entry": entry}).encode())
                except Exception as e:  # bad payload -> 400, never crash
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(f"bad payload: {e}".encode())

            def log_message(self, *args):
                pass  # stay quiet

        self._server = HTTPServer(("127.0.0.1", port), Handler)
        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()
