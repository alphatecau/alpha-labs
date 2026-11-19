"""Offline contract tests for the non-production Drive evidence adapter."""
import hashlib
import unittest
from tools.level3_staging.drive_custody import create_and_verify, reconcile_existing, DriveCustodyDenied

FOLDER = "118pwq_VOAGeeS1NOTXmoA4ZVEx4AcMo6"
NONCE = "a" * 64
DATA = b"test evidence only"
DIGEST = hashlib.sha256(DATA).hexdigest()

class Client:
    def __init__(self, *, tamper=False, fail=False):
        self.objects = {}
        self.tamper = tamper
        self.fail = fail
    def create(self, folder, name, payload):
        if self.fail:
            raise TimeoutError("ambiguous upload")
        self.objects["object_123456789"] = payload
        return "object_123456789"
    def lookup(self, folder, name):
        return list(self.objects)
    def read(self, object_id):
        return b"tampered" if self.tamper else self.objects[object_id]

class DriveCustodyTests(unittest.TestCase):
    def test_create_readback_receipt_not_auditor_approved(self):
        result = create_and_verify(Client(), FOLDER, NONCE, DIGEST, DATA)
        self.assertEqual(result["sha256"], DIGEST)
        self.assertFalse(result["auditor_anchor_verified"])
    def test_tampered_readback_denied(self):
        with self.assertRaises(DriveCustodyDenied):
            create_and_verify(Client(tamper=True), FOLDER, NONCE, DIGEST, DATA)
    def test_ambiguous_upload_denied(self):
        with self.assertRaisesRegex(DriveCustodyDenied, "reconcile"):
            create_and_verify(Client(fail=True), FOLDER, NONCE, DIGEST, DATA)
    def test_recover_single_matching_object(self):
        client = Client()
        client.objects["object_123456789"] = DATA
        receipt = reconcile_existing(client, FOLDER, NONCE, DIGEST, DATA)
        self.assertEqual(receipt["object_id"], "object_123456789")
        self.assertFalse(receipt["auditor_anchor_verified"])
    def test_missing_object_denied(self):
        with self.assertRaises(DriveCustodyDenied):
            reconcile_existing(Client(), FOLDER, NONCE, DIGEST, DATA)
    def test_duplicate_objects_denied(self):
        client = Client()
        client.objects["object_123456789"] = DATA
        client.objects["object_987654321"] = DATA
        with self.assertRaises(DriveCustodyDenied):
            reconcile_existing(client, FOLDER, NONCE, DIGEST, DATA)
    def test_recovery_tamper_denied(self):
        client = Client(tamper=True)
        client.objects["object_123456789"] = DATA
        with self.assertRaises(DriveCustodyDenied):
            reconcile_existing(client, FOLDER, NONCE, DIGEST, DATA)
    def test_bad_digest_denied(self):
        with self.assertRaises(DriveCustodyDenied):
            create_and_verify(Client(), FOLDER, NONCE, "b"*64, DATA)
    def test_oversize_denied(self):
        with self.assertRaises(DriveCustodyDenied):
            create_and_verify(Client(), FOLDER, NONCE, hashlib.sha256(b"x"*32769).hexdigest(), b"x"*32769)

if __name__ == "__main__":
    unittest.main()
