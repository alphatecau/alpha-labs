"""Offline tests for restricted Termux Level 3 staging."""
import json
import io
import contextlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.level3_staging.termux_local_approval import Refused, propose, approve, apply, main
from tools.level3_staging.termux_local_mcp import dispatch


class LocalStagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "docs" / "level3-staging").mkdir(parents=True)
        (self.root / "tests" / "level3-staging").mkdir(parents=True)

    def test_create_requires_local_approval_and_replay_denied(self):
        pending = propose(self.root, "docs/level3-staging/acceptance.md", "approved content")
        with self.assertRaises(Refused):
            apply(self.root, pending["request_id"])
        with patch("builtins.input", return_value="APPROVE"):
            approve(self.root, pending["request_id"])
        receipt = apply(self.root, pending["request_id"])
        self.assertEqual(receipt["status"], "complete")
        self.assertEqual((self.root / receipt["path"]).read_text(), "approved content")
        with self.assertRaises(Refused):
            apply(self.root, pending["request_id"])

    def test_cli_apply_requires_prior_approval(self):
        pending = propose(self.root, "docs/level3-staging/cli.md", "cli content")
        args = ["level3", "apply", pending["request_id"], "--root", str(self.root)]
        with patch("sys.argv", args), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as denied:
                main()
        self.assertIn("Denied", str(denied.exception))
        self.assertFalse((self.root / "docs/level3-staging/cli.md").exists())
        with patch("builtins.input", return_value="APPROVE"):
            approve(self.root, pending["request_id"])
        output = io.StringIO()
        with patch("sys.argv", args), contextlib.redirect_stdout(output):
            main()
        self.assertEqual(json.loads(output.getvalue())["status"], "complete")
        self.assertEqual((self.root / "docs/level3-staging/cli.md").read_text(), "cli content")
        with patch("sys.argv", args), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                main()

    def test_explicit_denial(self):
        pending = propose(self.root, "tests/level3-staging/probe.txt", "x")
        with patch("builtins.input", return_value="NO"), self.assertRaises(Refused):
            approve(self.root, pending["request_id"])
        with self.assertRaises(Refused):
            apply(self.root, pending["request_id"])

    def test_path_denial(self):
        for path in ("../escape", ".env", "docs/other.md", "docs/level3-staging/../evil.md"):
            with self.subTest(path=path), self.assertRaises(Refused):
                propose(self.root, path, "x")

    def test_existing_target_cannot_be_overwritten(self):
        target = self.root / "docs/level3-staging/existing.md"
        target.write_text("original")
        pending = propose(self.root, "docs/level3-staging/existing.md", "new")
        with patch("builtins.input", return_value="APPROVE"):
            approve(self.root, pending["request_id"])
        with self.assertRaises(FileExistsError):
            apply(self.root, pending["request_id"])
        self.assertEqual(target.read_text(), "original")

    def test_tamper_digest_denied(self):
        pending = propose(self.root, "docs/level3-staging/tamper.md", "original")
        with patch("builtins.input", return_value="APPROVE"):
            approve(self.root, pending["request_id"])
        record = self.root / ".level3-local-approvals" / (pending["request_id"] + ".json")
        data = json.loads(record.read_text())
        data["content"] = "changed"
        record.write_text(json.dumps(data))
        with self.assertRaises(Refused):
            apply(self.root, pending["request_id"])

    def test_mcp_does_not_expose_shell_or_unrestricted_write(self):
        listing = dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, self.root)
        self.assertEqual([x["name"] for x in listing["result"]["tools"]],
                         ["level3_propose_create", "level3_apply_approved_create"])
        denied = dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                           "params": {"name": "shell", "arguments": {"command": "id"}}}, self.root)
        self.assertTrue(denied["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
