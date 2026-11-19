"""Auditor-side full protocol integration using an isolated filesystem and test key.

No claim of real independent KMS, WORM retention or live Neon connectivity.
"""
import tempfile
import unittest
from unittest.mock import patch, Mock
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.level3_staging.auditor_checkpoint import CheckpointDenied, sign_and_retain, verify_sign_and_retain
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

    def test_full_chain_verification_to_two_persisted_signed_checkpoints(self):
        conn = Mock()
        first = {"count": 1, "last_sequence": 1, "head_hash": "a" * 64}
        second = {"count": 2, "last_sequence": 2, "head_hash": "b" * 64}
        conn.execute.return_value.fetchone.return_value = ("a" * 64,)
        with patch("tools.level3_staging.auditor_checkpoint.verify_audit_chain",
                   side_effect=[first, second]) as verify:
            one = verify_sign_and_retain(conn, self.audience, self.signer,
                                         self.store, self.public_key)
            two = verify_sign_and_retain(conn, self.audience, self.signer,
                                         self.store, self.public_key)
        self.assertEqual(verify.call_count, 2)
        self.assertEqual(one["signed"]["receipt"]["head_hash"], "a" * 64)
        self.assertEqual(two["signed"]["receipt"]["head_hash"], "b" * 64)
        self.assertEqual(self.store.read_latest(self.audience)["receipt"]["count"], 2)

    def test_tampered_stored_head_denied_before_chain_read(self):
        sign_and_retain(self.receipt(1, "a" * 64), self.signer,
                        self.store, self.public_key)
        latest = self.store.read_latest(self.audience)
        latest["receipt"]["head_hash"] = "c" * 64
        self.assertTrue(self.store.advance_latest(
            self.audience, self.receipt(1, "a" * 64), latest))
        with patch("tools.level3_staging.auditor_checkpoint.verify_audit_chain") as verify:
            with self.assertRaises(ValueError):
                verify_sign_and_retain(Mock(), self.audience, self.signer,
                                       self.store, self.public_key)
            verify.assert_not_called()

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
