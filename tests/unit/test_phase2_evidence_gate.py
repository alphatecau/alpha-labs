import base64
import hashlib
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from alpha_lab.research.phase2_evidence_gate import evaluate_archived_research_evidence

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
except ImportError:
    Ed25519PrivateKey = None


class EvidenceGateTests(unittest.TestCase):
    def test_valid_synthetic_archive_remains_unpromotable(self):
        if Ed25519PrivateKey is None:
            self.skipTest("Dedicated crypto CI requires cryptography")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "archive"
            research = root / "research"
            manifest = root / "manifest"
            signature = root / "signature"
            archive.write_bytes(b"synthetic evidence")
            research.write_bytes(archive.read_bytes())
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            payload = json.dumps({
                "archive_id": "snapshot-1", "capture_time": "2025-01-02T00:00:00Z",
                "publication_time": "2025-01-01T00:00:00Z",
                "archive_sha256": digest, "research_sha256": digest,
            }).encode()
            private = Ed25519PrivateKey.generate()
            public = private.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw)
            manifest.write_bytes(payload)
            signature.write_bytes(base64.b64encode(private.sign(payload)))
            decision = datetime(2025, 1, 3, tzinfo=timezone.utc)
            availability = dict(
                decision_time=decision,
                publication_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
                archive_capture_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                research_download_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
                source_id="source-1", content_sha256=digest, archived_content_sha256=digest,
                archive_provider="provider-1", archive_record_id="snapshot-1")
            provenance = dict(
                archive_path=archive, research_path=research,
                manifest_path=manifest, signature_path=signature,
                expected_archive_id="snapshot-1", decision_time=decision,
                trust_registry={"provider-1": {"onboarding": "independently_verified",
                                                "ed25519_public_key": public}},
                provider_id="provider-1")
            result = evaluate_archived_research_evidence(
                availability=availability, provenance=provenance)
            self.assertFalse(result["eligible_for_strategy_promotion"])
            self.assertFalse(result["eligible_for_live_trading"])
            self.assertFalse(result["historical_capture_independently_attested"])
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                evaluate_archived_research_evidence(
                    availability=dict(availability, archive_record_id="different"),
                    provenance=provenance)
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                evaluate_archived_research_evidence(
                    availability=dict(availability, content_sha256="0" * 64,
                                      archived_content_sha256="0" * 64),
                    provenance=provenance)
            with self.assertRaisesRegex(ValueError, "provider identity mismatch"):
                evaluate_archived_research_evidence(
                    availability=dict(availability, archive_provider="other"),
                    provenance=provenance)
            with self.assertRaisesRegex(ValueError, "Decision time mismatch"):
                evaluate_archived_research_evidence(
                    availability=dict(availability, decision_time=datetime(2025, 1, 4, tzinfo=timezone.utc)),
                    provenance=provenance)
            archive.write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "checksum"):
                evaluate_archived_research_evidence(
                    availability=availability, provenance=provenance)


if __name__ == "__main__":
    unittest.main()
