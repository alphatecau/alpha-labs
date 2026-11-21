"""Offline signed-approval regression tests."""
import base64
import hashlib
import importlib.util
from pathlib import Path
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools/level3_staging"
spec = importlib.util.spec_from_file_location("signed_approval", TOOLS / "signed_approval.py")
approval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(approval)


class SignedApprovalTests(unittest.TestCase):
    def setUp(self):
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        except ImportError:
            self.skipTest("cryptography dependency unavailable")
        self.key = Ed25519PrivateKey.generate()
        self.public = base64.b64encode(self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
        self.path = "docs/level3-staging/approval.md"
        self.content = b"approved"
        self.payload = {"version": 1, "operation": "create", "environment": "level3-staging",
                        "path": self.path, "sha256": hashlib.sha256(self.content).hexdigest(),
                        "nonce": "a" * 32, "expires_at": 1100}

    def signed(self):
        return base64.b64encode(self.key.sign(approval.canonical(self.payload))).decode()

    def test_valid(self):
        self.assertEqual(approval.verify(self.payload, self.signed(), self.public, self.path,
                                         self.content, now=1000)["nonce"], "a" * 32)

    def test_modified_content(self):
        signature = self.signed()
        with self.assertRaises(approval.ApprovalDenied):
            approval.verify(self.payload, signature, self.public, self.path, b"changed", now=1000)

    def test_modified_path(self):
        with self.assertRaises(approval.ApprovalDenied):
            approval.verify(self.payload, self.signed(), self.public, "docs/level3-staging/other.md",
                            self.content, now=1000)

    def test_expired(self):
        with self.assertRaises(approval.ApprovalDenied):
            approval.verify(self.payload, self.signed(), self.public, self.path, self.content, now=1100)

    def test_wrong_key(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        other = Ed25519PrivateKey.generate().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        with self.assertRaises(approval.ApprovalDenied):
            approval.verify(self.payload, self.signed(), base64.b64encode(other).decode(),
                            self.path, self.content, now=1000)

    def test_extra_field(self):
        self.payload["command"] = "shell"
        with self.assertRaises(approval.ApprovalDenied):
            approval.canonical(self.payload)

    def test_excessive_lifetime(self):
        with self.assertRaises(approval.ApprovalDenied):
            approval.verify(self.payload, self.signed(), self.public, self.path, self.content, now=1)


if __name__ == "__main__":
    unittest.main()
