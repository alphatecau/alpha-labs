"""Offline deny-by-default tests for Level 3 sync wrapper."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

script = Path(__file__).resolve().parents[1] / "tools" / "termux_level3_sync.py"
spec = importlib.util.spec_from_file_location("level3", script)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Level3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        (self.checkout / "tools").mkdir()
        (self.checkout / "tools" / "termux_approved_sync.py").write_text("# fixture")
        self.state = self.root / "private"
        self.state.mkdir(mode=0o700)
        self.conf = self.root / "config.json"
        self.conf.write_text(json.dumps({"repo":m.REPO,"checkout":str(self.checkout)}))
        self.sha = "a"*40
    def call(self, action, sha=None):
        args = ["--config",str(self.conf),"--state-dir",str(self.state),action]
        if sha is not None:
            args += ["--commit",sha]
        return m.main(args)
    def test_reject_wrong_repository(self):
        self.conf.write_text(json.dumps({"repo":"attacker/repo","checkout":str(self.checkout)}))
        with self.assertRaises(m.Refused):
            self.call("plan",self.sha)
    def test_reject_world_readable_state(self):
        self.state.chmod(0o755)
        with self.assertRaises(m.Refused):
            self.call("plan",self.sha)
    def test_reject_invalid_sha(self):
        with self.assertRaises(m.Refused):
            self.call("plan","main")
    def test_apply_requires_local_approval(self):
        with self.assertRaises(m.Refused):
            self.call("apply",self.sha)
    def test_local_approval_one_use(self):
        with patch.object(m,"run_sync",return_value="PASS") as mock:
            self.call("authorise",self.sha)
            self.assertEqual(self.call("apply",self.sha),"PASS")
            with self.assertRaises(m.Refused):
                self.call("apply",self.sha)
            self.assertEqual(mock.call_count,2)
    def test_wrong_sha_does_not_consume_grant(self):
        with patch.object(m,"run_sync",return_value="PASS"):
            self.call("authorise",self.sha)
            with self.assertRaises(m.Refused):
                self.call("apply","b"*40)
            self.assertTrue((self.state/"sync-approval.json").exists())
    def test_reject_symlink_grant(self):
        (self.state/"sync-approval.json").symlink_to(self.conf)
        with self.assertRaises(m.Refused):
            self.call("apply",self.sha)
    def test_recover_status_no_approval(self):
        with patch.object(m,"run_sync",return_value="RECOVERY") as mock:
            self.assertEqual(self.call("recover-status"),"RECOVERY")
            mock.assert_called_once_with(self.checkout,"recover")

if __name__ == "__main__":
    unittest.main()
