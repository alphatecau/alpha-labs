"""MCP signed write protocol regression tests."""
import base64
import hashlib
import tempfile
import time
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from tools.level3_staging.mcp_signed import dispatch
from tools.level3_staging.signed_create import canonical

class SignedMCPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"workspace"
        (self.root/"docs/level3-staging").mkdir(parents=True)
        self.db=Path(self.tmp.name)/"ledger.db"
        key=Ed25519PrivateKey.generate()
        self.pub=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self.path="docs/level3-staging/mcp.md"
        self.approval={"operation":"create","path":self.path,"sha256":hashlib.sha256(b"hello").hexdigest(),
                       "nonce":"b"*64,"expires_at":int(time.time())+120}
        self.sig=base64.b64encode(key.sign(canonical(self.approval))).decode()

    def request(self,name="level3_apply_signed_create",**updates):
        args={"path":self.path,"content":"hello","approval":self.approval,"signature":self.sig}
        args.update(updates)
        return dispatch({"jsonrpc":"2.0","id":1,"method":"tools/call",
                         "params":{"name":name,"arguments":args}},self.root,self.db,self.pub)["result"]

    def test_tools_list(self):
        result=dispatch({"jsonrpc":"2.0","id":1,"method":"tools/list"},self.root,self.db,self.pub)
        self.assertEqual([t["name"] for t in result["result"]["tools"]],["level3_apply_signed_create"])

    def test_valid_then_replay(self):
        self.assertNotIn("isError",self.request())
        self.assertEqual((self.root/self.path).read_text(),"hello")
        self.assertTrue(self.request()["isError"])

    def test_missing_signature(self):
        self.assertTrue(self.request(signature="")["isError"])
        self.assertFalse((self.root/self.path).exists())

    def test_tampered_content(self):
        self.assertTrue(self.request(content="evil")["isError"])
        self.assertFalse((self.root/self.path).exists())

    def test_unauthorised_tool(self):
        self.assertTrue(self.request(name="shell_exec")["isError"])

    def test_traversal(self):
        self.assertTrue(self.request(path="../secrets")["isError"])

if __name__=="__main__":
    unittest.main()
