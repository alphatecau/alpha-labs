import copy
import hashlib
import sqlite3
import unittest
from signed_protocol_v4 import Rejected, authorize, signature_for, verify

KEY = b"k" * 32
DEVICE = "termux-device-01"
NOW = 1800000000

def sample():
    task = {"schema": 4, "device": DEVICE, "nonce": "a" * 32,
            "issued_at": NOW - 5, "expires_at": NOW + 120,
            "operation": "repo_status", "repo": "alpha-labs"}
    return {"task": task, "signature": signature_for(task, KEY)}

class ProtocolTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(verify(sample(), KEY, DEVICE, NOW)["operation"], "repo_status")
    def test_bad_signature(self):
        e = sample(); e["signature"] = "0" * 64
        with self.assertRaises(Rejected): verify(e, KEY, DEVICE, NOW)
    def test_wrong_device(self):
        with self.assertRaises(Rejected): verify(sample(), KEY, "other-device-01", NOW)
    def test_expired(self):
        with self.assertRaises(Rejected): verify(sample(), KEY, DEVICE, NOW + 121)
    def test_future(self):
        with self.assertRaises(Rejected): verify(sample(), KEY, DEVICE, NOW - 60)
    def test_long_lifetime(self):
        e = sample(); e["task"]["expires_at"] += 500
        e["signature"] = signature_for(e["task"], KEY)
        with self.assertRaises(Rejected): verify(e, KEY, DEVICE, NOW)
    def test_shell_denied_even_if_signed(self):
        e = sample(); e["task"]["operation"] = "shell"
        e["signature"] = signature_for(e["task"], KEY)
        with self.assertRaises(Rejected): verify(e, KEY, DEVICE, NOW)
    def test_other_repo_denied_even_if_signed(self):
        e = sample(); e["task"]["repo"] = "private"
        e["signature"] = signature_for(e["task"], KEY)
        with self.assertRaises(Rejected): verify(e, KEY, DEVICE, NOW)
    def test_extra_fields_denied(self):
        e = sample(); e["task"]["command"] = "echo hi"
        e["signature"] = signature_for(e["task"], KEY)
        with self.assertRaises(Rejected): verify(e, KEY, DEVICE, NOW)
    def test_boolean_schema_denied(self):
        e = sample(); e["task"]["schema"] = True
        with self.assertRaises(Rejected): verify(e, KEY, DEVICE, NOW)
    def test_tamper_denied(self):
        e = sample(); e["task"]["repo"] = "Q3HASH"
        with self.assertRaises(Rejected): verify(e, KEY, DEVICE, NOW)
    def test_short_key_denied(self):
        with self.assertRaises(Rejected): verify(sample(), b"short", DEVICE, NOW)
    def test_duplicate_nonce(self):
        db = sqlite3.connect(":memory:")
        authorize(sample(), KEY, DEVICE, db, NOW)
        with self.assertRaises(Rejected): authorize(sample(), KEY, DEVICE, db, NOW)
    def test_distinct_nonce(self):
        db = sqlite3.connect(":memory:")
        authorize(sample(), KEY, DEVICE, db, NOW)
        e = sample(); e["task"]["nonce"] = "b" * 32
        e["signature"] = signature_for(e["task"], KEY)
        self.assertEqual(authorize(e, KEY, DEVICE, db, NOW)["nonce"], "b" * 32)
    def test_missing_field(self):
        e = sample(); del e["task"]["repo"]
        with self.assertRaises(Rejected): verify(e, KEY, DEVICE, NOW)

if __name__ == "__main__":
    unittest.main()
