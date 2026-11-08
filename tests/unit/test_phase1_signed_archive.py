import base64
import hashlib
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from alpha_lab.research.phase1_signed_archive import verify_signed_archive

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
except ImportError:
    Ed25519PrivateKey = None
    serialization = None


class SignedArchiveTests(unittest.TestCase):
    def test_signed_bytes_and_tampering(self):
        if Ed25519PrivateKey is None:
            self.skipTest('cryptography unavailable in generic research runner; dedicated signed-archive CI requires it')
        with TemporaryDirectory() as folder:
            root = Path(folder)
            archive, research = root / "archive.bin", root / "research.bin"
            manifest_path, sig_path = root / "manifest.json", root / "manifest.sig"
            archive.write_bytes(b"authentic test fixture")
            research.write_bytes(archive.read_bytes())
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            manifest = {
                "archive_id": "snapshot-001",
                "capture_time": "2025-01-02T12:00:00Z",
                "publication_time": "2025-01-01T12:00:00Z",
                "archive_sha256": digest, "research_sha256": digest
            }
            private = Ed25519PrivateKey.generate()
            public = private.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw)
            payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            manifest_path.write_bytes(payload)
            sig_path.write_bytes(base64.b64encode(private.sign(payload)))
            kwargs = dict(archive_path=archive, research_path=research,
                          manifest_path=manifest_path, signature_path=sig_path,
                          trusted_ed25519_public_key=public,
                          expected_archive_id="snapshot-001",
                          decision_time=datetime(2025, 1, 3, tzinfo=timezone.utc))
            result = verify_signed_archive(**kwargs)
            self.assertTrue(result["signature_valid_for_supplied_trusted_key"])
            self.assertFalse(result["eligible_for_strategy_promotion"])
            research.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "checksum"):
                verify_signed_archive(**kwargs)
            research.write_bytes(archive.read_bytes())
            manifest_path.write_bytes(payload + b" ")
            with self.assertRaisesRegex(ValueError, "authentication"):
                verify_signed_archive(**kwargs)
            manifest_path.write_bytes(payload)
            with self.assertRaisesRegex(ValueError, "signature invalid"):
                verify_signed_archive(**dict(kwargs, trusted_ed25519_public_key=b"0" * 32))
            with self.assertRaisesRegex(ValueError, "identifier"):
                verify_signed_archive(**dict(kwargs, expected_archive_id="wrong"))
            with self.assertRaisesRegex(ValueError, "historical decision"):
                verify_signed_archive(**dict(kwargs, decision_time=datetime(2025, 1, 2, tzinfo=timezone.utc)))


if __name__ == "__main__":
    unittest.main()
