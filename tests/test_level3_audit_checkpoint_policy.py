import unittest

from tools.level3_staging.audit_checkpoint_policy import (
    CheckpointDenied,
    verify_checkpoint_metadata,
)


class CheckpointPolicyTests(unittest.TestCase):
    def setUp(self):
        self.checkpoint = {
            "audience": "level3-test",
            "sequence": 2,
            "head_hash": "a" * 64,
            "receipt_sha256": "b" * 64,
            "storage_domain": "offline-auditor",
        }

    def test_valid_metadata(self):
        self.assertTrue(verify_checkpoint_metadata(self.checkpoint, "level3-test"))

    def test_broker_storage_denied(self):
        self.checkpoint["storage_domain"] = "render-local"
        with self.assertRaises(CheckpointDenied):
            verify_checkpoint_metadata(self.checkpoint, "level3-test")

    def test_audience_mismatch_denied(self):
        with self.assertRaises(CheckpointDenied):
            verify_checkpoint_metadata(self.checkpoint, "other")

    def test_bad_hash_denied(self):
        self.checkpoint["head_hash"] = "xyz"
        with self.assertRaises(CheckpointDenied):
            verify_checkpoint_metadata(self.checkpoint, "level3-test")

    def test_boolean_sequence_denied(self):
        self.checkpoint["sequence"] = True
        with self.assertRaises(CheckpointDenied):
            verify_checkpoint_metadata(self.checkpoint, "level3-test")
