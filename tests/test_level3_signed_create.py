"""Signed staging write security tests; never connect to a live MCP server."""
import base64
import hashlib
import tempfile
import time
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from tools.level3_staging.signed_create import Denied, apply, canonical

class SignedCreateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "workspace"
        (self.root / "docs/level3-staging").mkdir(parents=True)
        self.db = Path(self.tmp.name) / "ledger.db"
        self.key = Ed25519PrivateKey.generate()
        self.pub = self.key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)
        self.path = "docs/level3-staging/example.md"
        self.content = "hello"
        self.approval = {
            "operation":"create", "path":self.path,
            "sha256":hashlib.sha256(self.content.encode()).hexdigest(),
            "nonce":"a"*64, "expires_at":1100,
        }

    def signed(self):
        return base64.b64encode(self.key.sign(canonical(self.approval))).decode()

    def invoke(self, content=None, path=None, signature=None):
        return apply(self.root, self.db, self.pub, self.approval,
                     self.signed() if signature is None else signature,
                     self.path if path is None else path,
                     self.content if content is None else content, now=1000)

    def test_valid_create(self):
        self.assertEqual(self.invoke()["status"], "complete")
        self.assertEqual((self.root / self.path).read_text(), "hello")

    def test_replay_denied(self):
        self.invoke()
        with self.assertRaises(Exception):
            self.invoke()

    def test_wrong_content(self):
        with self.assertRaises(Denied):
            self.invoke(content="changed")

    def test_wrong_signature(self):
        with self.assertRaises(Denied):
            self.invoke(signature=base64.b64encode(b"x"*64).decode())

    def test_expired(self):
        self.approval["expires_at"] = 1000
        with self.assertRaises(Denied):
            self.invoke()

    def test_path_traversal(self):
        with self.assertRaises(Denied):
            self.invoke(path="../escape")

    def test_existing_file(self):
        (self.root / self.path).write_text("original")
        with self.assertRaises(FileExistsError):
            self.invoke()
        self.assertEqual((self.root / self.path).read_text(), "original")

    def test_tampered_approval(self):
        signature = self.signed()
        self.approval["path"] = "docs/level3-staging/other.md"
        with self.assertRaises(Denied):
            self.invoke(signature=signature)

    def test_invalid_nonce(self):
        self.approval["nonce"] = "short"
        with self.assertRaises(Denied):
            self.invoke()

    def test_symlink_destination(self):
        outside = Path(self.tmp.name) / "outside"
        outside.write_text("unchanged")
        (self.root / self.path).symlink_to(outside)
        with self.assertRaises(FileExistsError):
            self.invoke()
        self.assertEqual(outside.read_text(), "unchanged")

    def test_ledger_outside_workspace(self):
        self.db = self.root / "ledger.db"
        with self.assertRaises(Denied):
            self.invoke()

    def test_claimed_after_failed_write_remains_consumed(self):
        (self.root / self.path).write_text("existing")
        with self.assertRaises(FileExistsError):
            self.invoke()
        (self.root / self.path).unlink()
        with self.assertRaises(Exception):
            self.invoke()

    def test_payload_limit(self):
        with self.assertRaises(Denied):
            self.invoke(content="a"*32769)

if __name__ == "__main__":
    unittest.main()
