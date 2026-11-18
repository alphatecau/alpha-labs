"""Operator signing policy tests."""
import base64
import os
import tempfile
import unittest
from pathlib import Path
from tools.level3_staging.operator_approval import sign
from tools.level3_staging.signed_create import canonical
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.key=Path(self.tmp.name)/"key"
        self.key.write_bytes(bytes(range(32)))
        self.key.chmod(0o600)

    def test_sign_exact_content(self):
        result=sign(self.key,"docs/level3-staging/example.md","test",now=1000,nonce="c"*64)
        approval=result["approval"]
        self.assertEqual(approval["expires_at"],1120)
        Ed25519PrivateKey.from_private_bytes(self.key.read_bytes()).public_key().verify(
            base64.b64decode(result["signature"]),canonical(approval))

    def test_world_readable_key_denied(self):
        self.key.chmod(0o644)
        with self.assertRaises(PermissionError):
            sign(self.key,"docs/level3-staging/example.md","test")

    def test_key_symlink_denied(self):
        link=Path(self.tmp.name)/"link"
        link.symlink_to(self.key)
        with self.assertRaises(PermissionError):
            sign(link,"docs/level3-staging/example.md","test")

    def test_non_allowlisted_path_denied(self):
        with self.assertRaises(Exception):
            sign(self.key,".env","secret")

    def test_long_expiry_denied(self):
        with self.assertRaises(ValueError):
            sign(self.key,"docs/level3-staging/example.md","test",ttl=601)

if __name__=="__main__":
    unittest.main()
