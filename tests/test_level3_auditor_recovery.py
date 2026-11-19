"""Crash/replay/tamper recovery inspection: never auto-promote evidence."""
import base64
import hashlib
import json
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from tools.level3_staging.auditor_recovery import RecoveryDenied, inspect_recovery
from tools.level3_staging.external_anchor import canonical_receipt

AUDIENCE = "alpha-labs-level3:staging"


class Local:
    def __init__(self, raw, latest=None):
        self.raw, self.latest = raw, latest
        self.writes = 0

    def read(self, key):
        return self.raw

    def read_latest(self, audience):
        return self.latest

    def advance_latest(self, *args):
        self.writes += 1
        raise AssertionError("recovery inspection must not advance latest")


class Drive:
    def __init__(self, raw):
        self.raw = raw

    def read(self, key):
        return self.raw


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        private = Ed25519PrivateKey.generate()
        self.private = private
        self.public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        receipt = {"version": 1, "audience": AUDIENCE, "count": 2,
                   "last_sequence": 2, "head_hash": "a" * 64}
        self.signed = {"receipt": receipt, "signature": base64.b64encode(
            private.sign(canonical_receipt(receipt))).decode()}
        self.raw = json.dumps(self.signed, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        self.key = (f"level3-checkpoints/alpha-labs-level3_staging/"
                    f"{2:020d}-{hashlib.sha256(self.raw).hexdigest()}.json")

    def inspect(self, local=None, drive=None):
        local = local or Local(self.raw)
        drive = drive or Drive(self.raw)
        return inspect_recovery(local, drive, self.key, AUDIENCE, self.public)

    def test_crash_before_cas_is_manual_review(self):
        local = Local(self.raw)
        result = self.inspect(local=local)
        self.assertEqual(result["state"], "unanchored_candidate_manual_review")
        self.assertFalse(result["promoted"])
        self.assertEqual(local.writes, 0)

    def test_replay_of_committed_checkpoint_is_idempotent(self):
        self.assertEqual(self.inspect(local=Local(self.raw, self.signed))["state"], "already_committed")

    def test_drive_tamper_rejected(self):
        with self.assertRaisesRegex(RecoveryDenied, "differ"):
            self.inspect(drive=Drive(b"tampered"))

    def test_missing_local_evidence_rejected(self):
        with self.assertRaises(RecoveryDenied):
            self.inspect(local=Local(b""))

    def test_wrong_object_key_rejected(self):
        with self.assertRaisesRegex(RecoveryDenied, "key mismatch"):
            inspect_recovery(Local(self.raw), Drive(self.raw), self.key.replace("00000000000000000002", "00000000000000000003"), AUDIENCE, self.public)

    def test_malformed_latest_rejected(self):
        with self.assertRaisesRegex(RecoveryDenied, "invalid trusted latest"):
            self.inspect(local=Local(self.raw, {"bad": True}))

    def test_missing_remote_evidence_rejected(self):
        class MissingDrive:
            def read(self, key):
                raise FileNotFoundError("missing")
        with self.assertRaisesRegex(RecoveryDenied, "unavailable"):
            self.inspect(drive=MissingDrive())

    def test_same_height_equivocation_rejected(self):
        old = dict(self.signed["receipt"], head_hash="b" * 64)
        latest = {"receipt": old, "signature": base64.b64encode(
            self.private.sign(canonical_receipt(old))).decode()}
        with self.assertRaises(ValueError):
            self.inspect(local=Local(self.raw, latest))

    def test_candidate_replay_older_than_latest_rejected(self):
        newer = dict(self.signed["receipt"], count=3, last_sequence=3, head_hash="c" * 64)
        latest = {"receipt": newer, "signature": base64.b64encode(
            self.private.sign(canonical_receipt(newer))).decode()}
        with self.assertRaises(ValueError):
            self.inspect(local=Local(self.raw, latest))

    def test_corrupt_signature_rejected(self):
        changed = json.loads(self.raw)
        changed["signature"] = base64.b64encode(b"z" * 64).decode()
        tampered = json.dumps(changed, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        with self.assertRaises(ValueError):
            self.inspect(local=Local(tampered), drive=Drive(tampered))


if __name__ == "__main__":
    unittest.main()
