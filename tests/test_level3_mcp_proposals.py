"""Protocol tests for Level 3 proposal-only MCP transport."""
import tempfile
import unittest
from pathlib import Path
from tools.level3_staging.mcp_proposals import dispatch

class TestProposalMCP(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "docs/level3-staging").mkdir(parents=True)

    def request(self, method, params=None):
        return dispatch({"jsonrpc":"2.0","id":1,"method":method,"params":params or {}}, self.root)

    def test_initialize(self):
        self.assertEqual(self.request("initialize")["result"]["serverInfo"]["name"], "alpha-labs-level3-proposal-only")

    def test_only_proposal_tool(self):
        tools = self.request("tools/list")["result"]["tools"]
        self.assertEqual([x["name"] for x in tools], ["level3_propose_create"])

    def test_proposal_no_write(self):
        target = self.root / "docs/level3-staging/test.md"
        result = self.request("tools/call", {"name":"level3_propose_create","arguments":{"path":"docs/level3-staging/test.md","content":"hello"}})
        self.assertIn("sha256", result["result"]["content"][0]["text"])
        self.assertFalse(target.exists())

    def test_refuses_existing_target_without_crash(self):
        (self.root / 'docs/level3-staging/existing.md').write_text('original')
        result = self.request('tools/call', {'name':'level3_propose_create','arguments':{'path':'docs/level3-staging/existing.md','content':'replacement'}})
        self.assertTrue(result['result']['isError'])
        self.assertEqual((self.root / 'docs/level3-staging/existing.md').read_text(), 'original')

    def test_refuses_unlisted_tool(self):
        result = self.request("tools/call", {"name":"level3_apply_create","arguments":{}})
        self.assertTrue(result["result"]["isError"])

    def test_refuses_traversal(self):
        result = self.request("tools/call", {"name":"level3_propose_create","arguments":{"path":"../secrets","content":"x"}})
        self.assertTrue(result["result"]["isError"])

if __name__ == "__main__":
    unittest.main()
