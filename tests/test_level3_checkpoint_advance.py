import unittest

from tools.level3_staging.audit_checkpoint_policy import CheckpointDenied
from tools.level3_staging.checkpoint_advance import verify_checkpoint_advance


def checkpoint(sequence, head="a" * 64, domain="independent-auditor-drive"):
    return {
        "audience": "alpha-labs-level3", "sequence": sequence,
        "head_hash": head, "receipt_sha256": "c" * 64,
        "storage_domain": domain,
    }


class CheckpointAdvanceTests(unittest.TestCase):
    def test_valid_advance(self):
        self.assertTrue(verify_checkpoint_advance(
            checkpoint(1), checkpoint(2, "b" * 64), "alpha-labs-level3",
        ))

    def test_replay_denied(self):
        with self.assertRaises(CheckpointDenied):
            verify_checkpoint_advance(checkpoint(2), checkpoint(2, "b" * 64), "alpha-labs-level3")

    def test_rollback_denied(self):
        with self.assertRaises(CheckpointDenied):
            verify_checkpoint_advance(checkpoint(2), checkpoint(1, "b" * 64), "alpha-labs-level3")

    def test_same_head_denied(self):
        with self.assertRaises(CheckpointDenied):
            verify_checkpoint_advance(checkpoint(1), checkpoint(2), "alpha-labs-level3")

    def test_storage_switch_denied(self):
        with self.assertRaises(CheckpointDenied):
            verify_checkpoint_advance(
                checkpoint(1), checkpoint(2, "b" * 64, "offline-auditor"), "alpha-labs-level3",
            )

    def test_audience_mismatch_denied(self):
        with self.assertRaises(CheckpointDenied):
            verify_checkpoint_advance(checkpoint(1), checkpoint(2, "b" * 64), "wrong-audience")

    def test_boolean_sequence_denied(self):
        with self.assertRaises(CheckpointDenied):
            verify_checkpoint_advance(checkpoint(True), checkpoint(2, "b" * 64), "alpha-labs-level3")
