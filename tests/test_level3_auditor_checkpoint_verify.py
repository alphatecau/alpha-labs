"""Read-only checkpoint verification detects tampering and missing mirrors."""
import base64
import hashlib
import json
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from tools.level3_staging import auditor_checkpoint_verify as verifier
from tools.level3_staging.external_anchor import canonical_receipt


class Store:
    def __init__(self, signed, raw):
        self.signed = signed
        self.raw = raw

    def read_latest(self, audience):
        return self.signed

    def read(self, key):
        return self.raw


class Drive:
    def __init__(self, raw):
        self.raw = raw

    def read(self, key):
        return self.raw


class CheckpointVerificationTests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        receipt = {"version": 1, "audience": verifier.AUDIENCE,
                   "count": 2, "last_sequence": 2, "head_hash": "a" * 64}
        self.signed = {"receipt": receipt, "signature": base64.b64encode(
            self.private.sign(canonical_receipt(receipt))).decode("ascii")}
        self.raw = json.dumps(self.signed, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

    def verify(self, local=None, remote=None, signed=None):
        with patch.object(verifier, "PUBLIC_KEY", self.public):
            return verifier.verify(Store(self.signed if signed is None else signed,
                                         self.raw if local is None else local),
                                   Drive(self.raw if remote is None else remote))

    def test_valid_checkpoint(self):
        self.assertEqual(self.verify()["sha256"], hashlib.sha256(self.raw).hexdigest())

    def test_altered_drive_bytes_rejected(self):
        with self.assertRaisesRegex(ValueError, "remote Drive checkpoint"):
            self.verify(remote=b"altered")

    def test_missing_local_object_rejected(self):
        with self.assertRaisesRegex(ValueError, "local signed checkpoint"):
            self.verify(local=b"")

    def test_tampered_latest_receipt_rejected(self):
        tampered = json.loads(self.raw)
        tampered["receipt"]["head_hash"] = "b" * 64
        with self.assertRaises(ValueError):
            self.verify(signed=tampered)

    def test_missing_latest_rejected(self):
        with patch.object(verifier, "PUBLIC_KEY", self.public):
            with self.assertRaisesRegex(ValueError, "missing or invalid trusted"):
                verifier.verify(Store(None, self.raw), Drive(self.raw))


if __name__ == "__main__":
    unittest.main()
