"""Tests for the fail-closed Level 3 proposal-only MCP dispatcher."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools/level3_staging"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("proposal_only_mcp", TOOLS / "proposal_only_mcp.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProposalOnlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def call(self, name, args):
        return module.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": name, "arguments": args}}, self.root)

    def test_list_only_propose(self):
        result = module.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, self.root)
        self.assertEqual([x["name"] for x in result["result"]["tools"]], ["level3_propose_create"])

    def test_propose_does_not_create_target(self):
        path = "docs/level3-staging/proposal.md"
        receipt = self.call("level3_propose_create", {"path": path, "content": "test"})
        self.assertFalse(receipt["result"].get("isError", False))
        self.assertFalse((self.root / path).exists())
        self.assertEqual(json.loads(receipt["result"]["content"][0]["text"])["status"], "pending")

    def test_apply_tool_refused(self):
        reply = self.call("level3_apply_approved_create", {"request_id": "a" * 32})
        self.assertTrue(reply["result"]["isError"])

    def test_unknown_method_refused(self):
        reply = module.dispatch({"jsonrpc": "2.0", "id": 1, "method": "shell/exec"}, self.root)
        self.assertEqual(reply["error"]["code"], -32601)

    def test_path_escape_refused(self):
        reply = self.call("level3_propose_create", {"path": "../outside", "content": "x"})
        self.assertTrue(reply["result"]["isError"])

    def test_extra_arguments_refused(self):
        reply = self.call("level3_propose_create",
                          {"path": "docs/level3-staging/a.md", "content": "x", "shell": "whoami"})
        self.assertTrue(reply["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
