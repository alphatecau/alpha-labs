import hashlib
import unittest

from tools.level3_staging.drive_readback import (
    CustodyReadbackDenied,
    verify_drive_readback,
)


class DriveReadbackTests(unittest.TestCase):
    def setUp(self):
        self.payload = b"encrypted-custody-test-fixture"
        self.digest = hashlib.sha256(self.payload).hexdigest()

    def test_exact_readback(self):
        self.assertEqual(
            verify_drive_readback(self.digest, self.payload, self.payload),
            {"sha256": self.digest, "size": len(self.payload)},
        )

    def test_modified_readback_denied(self):
        with self.assertRaises(CustodyReadbackDenied):
            verify_drive_readback(self.digest, self.payload, self.payload + b"x")

    def test_wrong_upload_digest_denied(self):
        with self.assertRaises(CustodyReadbackDenied):
            verify_drive_readback("0" * 64, self.payload, self.payload)

    def test_invalid_expected_digest_denied(self):
        with self.assertRaises(CustodyReadbackDenied):
            verify_drive_readback("not-a-sha256", self.payload, self.payload)

    def test_nonbytes_readback_denied(self):
        with self.assertRaises(CustodyReadbackDenied):
            verify_drive_readback(self.digest, self.payload, self.payload.decode())

    def test_empty_object(self):
        digest = hashlib.sha256(b"").hexdigest()
        self.assertEqual(verify_drive_readback(digest, b"", b"")["size"], 0)


if __name__ == "__main__":
    unittest.main()
