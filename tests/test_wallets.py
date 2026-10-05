"""Payouts: sweep accounting never double-counts."""
import json
import os
import tempfile

from juggernaut.wallets import ManualBackend, total_swept, write_instruction

import pytest


def test_sweep_instruction_and_accounting():
    d = tempfile.mkdtemp()
    assert total_swept(d) == 0
    p = write_instruction(d, "bc1qtest", 5000)
    assert os.path.exists(p)
    assert total_swept(d) == 5000  # pending counts -- no double-sweep
    # mark done, still counted once
    with open(p) as f:
        e = json.load(f)
    e["status"] = "done"
    with open(p, "w") as f:
        json.dump(e, f)
    assert total_swept(d) == 5000


def test_bad_sats_rejected():
    d = tempfile.mkdtemp()
    with pytest.raises(ValueError):
        write_instruction(d, "bc1qtest", 0)
    with pytest.raises(ValueError):
        write_instruction(d, "bc1qtest", -5)


def test_manual_backend_has_no_keys():
    with pytest.raises(RuntimeError):
        ManualBackend().send("bc1qtest", 100)
