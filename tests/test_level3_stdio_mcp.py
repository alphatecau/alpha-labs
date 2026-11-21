"""Protocol and safety regression tests for the local Level 3 stdio MCP adapter."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from tools.level3_staging.stdio_server import serve


class Level3StdioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def exchange(self, messages):
        src = io.BytesIO(b"".join(json.dumps(m).encode() + b"\n" for m in messages))
        out = io.StringIO()
        serve(self.root, src, out)
        return [json.loads(line) for line in out.getvalue().splitlines()]

    def test_initialize_and_only_proposal_tool(self):
        a = self.exchange([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ])
        self.assertEqual(len(a), 2)
        self.assertEqual(a[0]["result"]["serverInfo"]["name"], "level3-proposal-only")
        self.assertEqual([t["name"] for t in a[1]["result"]["tools"]], ["level3_propose_create"])

    def test_propose_not_apply(self):
        a = self.exchange([
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "level3_propose_create",
                        "arguments": {"path": "docs/level3-staging/a.md", "content": "draft"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "level3_apply_approved_create", "arguments": {}}},
        ])
        self.assertFalse(a[0]["result"].get("isError", False))
        self.assertTrue(a[1]["result"]["isError"])
        self.assertFalse((self.root / "docs/level3-staging/a.md").exists())

    def test_invalid_and_oversize_fail_closed(self):
        out = io.StringIO()
        serve(self.root, io.BytesIO(b"not-json\n" + b"x" * 65537 + b"\n" +
              b'{"jsonrpc":"2.0","id":5,"method":"shell/exec"}\n'), out)
        result = json.loads(out.getvalue())
        self.assertEqual(result["error"]["code"], -32601)

    def test_path_escape_refused(self):
        a = self.exchange([{"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                            "params": {"name": "level3_propose_create",
                                       "arguments": {"path": "../outside", "content": "x"}}}])
        self.assertTrue(a[0]["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
