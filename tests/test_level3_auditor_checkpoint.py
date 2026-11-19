import json
import unittest
from unittest.mock import Mock
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tools.level3_staging.auditor_checkpoint import (
    CheckpointDenied, build_checkpoint, sign_and_retain,
)


class MemoryCreateOnlyStore:
    def __init__(self):
        self.data = {}

    def create_once(self, key, raw):
        if key in self.data:
            raise ValueError("overwrite forbidden")
        self.data[key] = raw

    def read(self, key):
        return self.data[key]


class AuditorCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        self.public = self.key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.store = MemoryCreateOnlyStore()
        self.receipt = {
            "version": 1, "audience": "alpha-labs-level3:staging",
            "count": 2, "last_sequence": 2, "head_hash": "a" * 64,
        }

    def test_sign_persist_readback_verify(self):
        result = sign_and_retain(self.receipt, self.key, self.store, self.public)
        self.assertIn(result["key"], self.store.data)
        self.assertEqual(json.loads(self.store.read(result["key"]))["receipt"], self.receipt)

    def test_wrong_signer_key_denied_before_store(self):
        with self.assertRaises(ValueError):
            sign_and_retain(self.receipt, Ed25519PrivateKey.generate(), self.store, self.public)
        self.assertEqual(self.store.data, {})

    def test_duplicate_checkpoint_denied(self):
        with self.assertRaises(CheckpointDenied):
            sign_and_retain(self.receipt, self.key, self.store, self.public, previous=self.receipt)

    def test_readback_corruption_denied(self):
        self.store.read = lambda key: b"corrupted"
        with self.assertRaises(CheckpointDenied):
            sign_and_retain(self.receipt, self.key, self.store, self.public)

    def test_empty_chain_denied(self):
        conn = Mock()
        with unittest.mock.patch(
            "tools.level3_staging.auditor_checkpoint.verify_audit_chain",
            return_value={"count": 0, "last_sequence": 0, "head_hash": "0" * 64},
        ):
            with self.assertRaises(CheckpointDenied):
                build_checkpoint(conn, self.receipt["audience"])

    def test_ancestor_mismatch_denied(self):
        conn = Mock()
        conn.execute.return_value.fetchone.return_value = ("b" * 64,)
        previous = {"version": 1, "audience": self.receipt["audience"],
                    "count": 1, "last_sequence": 1, "head_hash": "c" * 64}
        with unittest.mock.patch(
            "tools.level3_staging.auditor_checkpoint.verify_audit_chain",
            return_value={"count": 2, "last_sequence": 2, "head_hash": "a" * 64},
        ):
            with self.assertRaises(CheckpointDenied):
                build_checkpoint(conn, self.receipt["audience"], previous=previous)


if __name__ == "__main__":
    unittest.main()
