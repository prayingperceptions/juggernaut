"""The cage: allowlist, approvals, kill switch."""
import os
import tempfile

from juggernaut.cage import Cage


def test_allowlist():
    c = Cage(allowed_actions=["wait", "check_earnings"])
    assert c.check("wait")[0] is True
    ok, reason = c.check("rm_rf")
    assert ok is False and "allowlisted" in reason


def test_approvals_required():
    c = Cage(allowed_actions=["broadcast"], approvals_required=["broadcast"])
    ok, reason = c.check("broadcast")
    assert ok is False and "approval" in reason
    c2 = Cage(allowed_actions=["broadcast"], approvals_required=["broadcast"],
              auto_approve=True)
    assert c2.check("broadcast")[0] is True


def test_kill_switch():
    d = tempfile.mkdtemp()
    kf = os.path.join(d, "KILL")
    c = Cage(allowed_actions=[], kill_file=kf)
    assert c.kill_requested() is False
    open(kf, "w").close()
    assert c.kill_requested() is True
