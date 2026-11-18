"""Offline regression tests for interrupted sync state recovery."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "termux_approved_sync.py"
spec = importlib.util.spec_from_file_location("termux_sync", SCRIPT)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

class RecoveryTests(unittest.TestCase):
    def run_case(self, head, approved, expected_phase, expect_record):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "state.json"
            data = {"before": "a"*40, "after": "b"*40, "backup": "termux-sync-backup/test", "phase": "pending"}
            state.write_text(json.dumps(data))
            def fake_git(*args, **kwargs):
                if args[0] == "rev-parse":
                    return (head, 0)
                raise AssertionError(args)
            with patch.object(sync, "require_repository", return_value=state), patch.object(sync, "require_clean"), patch.object(sync, "commit", return_value=head), patch.object(sys, "argv", ["sync", "recover"] + (["--approve"] if approved else [])):
                sync.main()
            self.assertEqual(state.exists(), expect_record)
            if expect_record:
                self.assertEqual(json.loads(state.read_text())["phase"], expected_phase)

    def test_before_approval(self):
        self.run_case("a"*40, False, "pending", True)

    def test_before_approved(self):
        self.run_case("a"*40, True, None, False)

    def test_after_approval(self):
        self.run_case("b"*40, False, "pending", True)

    def test_after_approved(self):
        self.run_case("b"*40, True, "applied", True)

    def test_unknown_head_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "state.json"
            state.write_text(json.dumps({"before": "a"*40, "after": "b"*40, "phase": "pending"}))
            with patch.object(sync, "require_repository", return_value=state), patch.object(sync, "require_clean"), patch.object(sync, "commit", return_value="c"*40), patch.object(sys, "argv", ["sync", "recover", "--approve"]):
                with self.assertRaises(sync.SyncError):
                    sync.main()

if __name__ == "__main__":
    unittest.main()
