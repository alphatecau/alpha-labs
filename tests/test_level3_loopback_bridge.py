"""Loopback MCP bridge security and protocol tests, no network tunnel."""
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from tools.level3_staging.loopback_bridge import handler_for

TOKEN = "test-only-secret-" + "x" * 40


class LoopbackBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.root, TOKEN))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method="POST", path="/mcp", payload=None, token=TOKEN, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        data = json.dumps(payload).encode() if payload is not None else b"{}"
        h = {"Content-Type": "application/json"}
        if token is not None:
            h["Authorization"] = "Bearer " + token
        if headers:
            h.update(headers)
        conn.request(method, path, body=data if method == "POST" else None, headers=h)
        response = conn.getresponse()
        status, body = response.status, response.read()
        conn.close()
        return status, json.loads(body) if body and body.startswith(b"{") else body

    def test_only_loopback_listener(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_unauthorised_refused(self):
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        self.assertEqual(self.request(payload=message, token=None)[0], 401)
        self.assertEqual(self.request(payload=message, token="wrong")[0], 401)

    def test_tool_list_proposal_only(self):
        status, result = self.request(payload={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(status, 200)
        self.assertEqual([t["name"] for t in result["result"]["tools"]], ["level3_propose_create"])

    def test_proposal_requires_local_approval(self):
        (self.root / "docs" / "level3-staging").mkdir(parents=True)
        status, result = self.request(payload={"jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "level3_propose_create",
                       "arguments": {"path": "docs/level3-staging/bridge.md", "content": "pending"}}})
        self.assertEqual(status, 200)
        self.assertFalse(result["result"].get("isError", False))
        self.assertFalse((self.root / "docs/level3-staging/bridge.md").exists())
        status, result = self.request(payload={"jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "level3_apply_approved_create", "arguments": {}}})
        self.assertTrue(result["result"]["isError"])
        self.assertEqual(status, 200)

    def test_shell_denied(self):
        status, result = self.request(payload={"jsonrpc": "2.0", "id": 5, "method": "shell/exec"})
        self.assertEqual(status, 200)
        self.assertEqual(result["error"]["code"], -32601)

    def test_size_and_media_type_restrictions(self):
        self.assertEqual(self.request(headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request(headers={"Content-Length": "999999"})[0], 413)

    def test_health_and_unknown_route(self):
        self.assertEqual(self.request(method="GET", path="/healthz")[0], 200)
        self.assertEqual(self.request(path="/other")[0], 404)


if __name__ == "__main__":
    unittest.main()
