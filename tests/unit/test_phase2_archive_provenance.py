import base64
import hashlib
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from alpha_lab.research.phase1_signed_archive import verify_signed_archive
from alpha_lab.research.phase2_archive_provenance import verify_archive_provenance

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
except ImportError:
    Ed25519PrivateKey = None


class ArchivePhase2Tests(unittest.TestCase):
    def test_stream_limits_and_provenance_fail_closed(self):
        if Ed25519PrivateKey is None:
            self.skipTest("cryptography missing from generic runner; mandatory in dedicated CI")
        with TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "archive"
            research = root / "research"
            manifest = root / "manifest"
            signature = root / "signature"
            archive.write_bytes(b"fixture")
            research.write_bytes(b"fixture")
            digest = hashlib.sha256(b"fixture").hexdigest()
            payload = json.dumps(dict(archive_id="a1", capture_time="2025-01-02T00:00:00Z",
                                      publication_time="2025-01-01T00:00:00Z",
                                      archive_sha256=digest, research_sha256=digest)).encode()
            private = Ed25519PrivateKey.generate()
            public = private.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw)
            manifest.write_bytes(payload)
            signature.write_bytes(base64.b64encode(private.sign(payload)))
            args = dict(archive_path=archive, research_path=research,
                        manifest_path=manifest, signature_path=signature,
                        expected_archive_id="a1",
                        decision_time=datetime(2025, 1, 3, tzinfo=timezone.utc))
            with self.assertRaisesRegex(ValueError, "size limit"):
                verify_signed_archive(**args, trusted_ed25519_public_key=public, max_file_bytes=3)
            result = verify_signed_archive(**args, trusted_ed25519_public_key=public)
            self.assertFalse(result["eligible_for_strategy_promotion"])
            with self.assertRaisesRegex(ValueError, "Unrecognised"):
                verify_archive_provenance(**args, trust_registry={}, provider_id="p1")
            with self.assertRaisesRegex(ValueError, "not independently"):
                verify_archive_provenance(**args, trust_registry={"p1": {"onboarding": "self_asserted",
                                         "ed25519_public_key": public}}, provider_id="p1")
            record = {"p1": {"onboarding": "independently_verified", "ed25519_public_key": public}}
            result = verify_archive_provenance(**args, trust_registry=record, provider_id="p1",
                                               attestation={"claim": "archived"})
            self.assertEqual(result["status"], "PROVENANCE_REVIEW_REQUIRED")
            self.assertFalse(result["historical_capture_independently_attested"])
            self.assertFalse(result["eligible_for_strategy_promotion"])
            archive.write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "checksum"):
                verify_archive_provenance(**args, trust_registry=record, provider_id="p1")
            archive.write_bytes(b"fixture")
            link = root / "link"
            link.symlink_to(archive)
            with self.assertRaisesRegex(ValueError, "non-symlink"):
                verify_signed_archive(**dict(args, archive_path=link),
                                      trusted_ed25519_public_key=public)


if __name__ == "__main__":
    unittest.main()
