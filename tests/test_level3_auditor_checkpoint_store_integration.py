"""Auditor-side full protocol integration using an isolated filesystem and test key.

No claim of real independent KMS, WORM retention or live Neon connectivity.
"""
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.level3_staging.auditor_checkpoint import CheckpointDenied, sign_and_retain
from tools.level3_staging.auditor_file_store import AuditorFileStore


class AuditorCheckpointStoreIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name) / "auditor"
        root.mkdir(mode=0o700)
        self.store = AuditorFileStore(root)
        self.signer = Ed25519PrivateKey.generate()
        self.public_key = self.signer.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.audience = "alpha-labs-level3:staging"

    def tearDown(self):
        self.temp.cleanup()

    def receipt(self, count, head):
        return {"version": 1, "audience": self.audience, "count": count,
                "last_sequence": count, "head_hash": head}

    def test_two_monotonic_signed_checkpoints_and_recovery(self):
        first = self.receipt(1, "a" * 64)
        second = self.receipt(2, "b" * 64)
        first_result = sign_and_retain(first, self.signer, self.store, self.public_key)
        self.assertEqual(self.store.read_latest(self.audience)["receipt"], first)
        second_result = sign_and_retain(
            second, self.signer, self.store, self.public_key, previous=first
        )
        self.assertEqual(self.store.read_latest(self.audience)["receipt"], second)
        self.assertNotEqual(first_result["key"], second_result["key"])
        self.assertEqual(len(list((self.store.root / "level3-checkpoints").rglob("*.json"))), 2)
        # Fresh adapter reads the persisted latest head after simulated process restart.
        reopened = AuditorFileStore(self.store.root)
        self.assertEqual(reopened.read_latest(self.audience)["receipt"], second)
        self.assertEqual(reopened.read(first_result["key"]), self.store.read(first_result["key"]))

    def test_stale_writer_rejected_without_advancing_head(self):
        first = self.receipt(1, "a" * 64)
        sign_and_retain(first, self.signer, self.store, self.public_key)
        with self.assertRaises(CheckpointDenied):
            sign_and_retain(self.receipt(2, "b" * 64), self.signer,
                            self.store, self.public_key)
        self.assertEqual(self.store.read_latest(self.audience)["receipt"], first)

    def test_same_height_equivocation_rejected(self):
        first = self.receipt(1, "a" * 64)
        sign_and_retain(first, self.signer, self.store, self.public_key)
        with self.assertRaises(ValueError):
            sign_and_retain(self.receipt(1, "b" * 64), self.signer,
                            self.store, self.public_key, previous=first)
        self.assertEqual(self.store.read_latest(self.audience)["receipt"], first)

    def test_failed_cas_retains_orphan_for_reconciliation(self):
        first = self.receipt(1, "a" * 64)
        sign_and_retain(first, self.signer, self.store, self.public_key)
        original = self.store.advance_latest
        self.store.advance_latest = lambda *args: False
        try:
            with self.assertRaises(CheckpointDenied):
                sign_and_retain(self.receipt(2, "b" * 64), self.signer,
                                self.store, self.public_key, previous=first)
        finally:
            self.store.advance_latest = original
        self.assertEqual(self.store.read_latest(self.audience)["receipt"], first)
        self.assertEqual(len(list((self.store.root / "level3-checkpoints").rglob("*.json"))), 2)


if __name__ == "__main__":
    unittest.main()
