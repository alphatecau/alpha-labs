"""Broker worker refuses missing broker and never uses local ledger."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools.level3_staging.broker import custody_check,request
from tools.level3_staging.mcp_broker_worker import dispatch
from tools.level3_staging.signed_create import Denied

class BrokerTests(unittest.TestCase):
    def test_no_socket_refused(self):
        with self.assertRaises(OSError):
            request("/nonexistent/level3.sock",{"path":"docs/level3-staging/a.md","content":"x",
                   "approval":{},"signature":"x"},timeout=.1)
    def test_invalid_request_denied(self):
        with self.assertRaises(Denied):
            request("/missing",{"extra":1})
    def test_custody_inside_workspace_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"root"
            root.mkdir()
            with self.assertRaises(Denied):
                custody_check(root,root/"ledger.db",root/"audit.jsonl")
    def test_broker_failure_fails_closed(self):
        message={"jsonrpc":"2.0","id":4,"method":"tools/call","params":{
            "name":"level3_apply_signed_create","arguments":{
                "path":"docs/level3-staging/a.md","content":"x","approval":{},"signature":"x"}}}
        with patch("tools.level3_staging.mcp_broker_worker.request",side_effect=OSError("offline")):
            result=dispatch(message,"/missing")
        self.assertTrue(result["result"]["isError"])
        self.assertEqual(result["result"]["content"][0]["text"],"broker write refused")
    def test_worker_lists_only_signed_tool(self):
        result=dispatch({"jsonrpc":"2.0","id":1,"method":"tools/list"},"/missing")
        self.assertEqual(len(result["result"]["tools"]),1)
        self.assertEqual(result["result"]["tools"][0]["name"],"level3_apply_signed_create")
    def test_worker_initializes_without_ledger(self):
        result=dispatch({"jsonrpc":"2.0","id":2,"method":"initialize"},"/missing")
        self.assertEqual(result["result"]["serverInfo"]["name"],"alpha-labs-level3-broker-worker")

if __name__=="__main__":
    unittest.main()
