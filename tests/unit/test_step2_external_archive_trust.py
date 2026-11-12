"""Step 2: no caller-provided trust assertion becomes independent provenance."""
import unittest
from unittest.mock import patch

from alpha_lab.research.phase2_archive_provenance import verify_archive_provenance
from alpha_lab.research.phase2_evidence_gate import evaluate_archived_research_evidence


class ArchiveTrustBoundary(unittest.TestCase):
    def test_unonboarded_key_rejected_before_signature_verification(self):
        with self.assertRaisesRegex(ValueError, "independently onboarded"):
            verify_archive_provenance(
                archive_path="unused", research_path="unused",
                manifest_path="unused", signature_path="unused",
                expected_archive_id="archive-1", decision_time="unused",
                trust_registry={"provider": {"onboarding": "self_declared",
                                             "ed25519_public_key": b"x" * 32}},
                provider_id="provider",
            )

    def test_unrecognised_provider_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unrecognised"):
            verify_archive_provenance(
                archive_path="unused", research_path="unused",
                manifest_path="unused", signature_path="unused",
                expected_archive_id="archive-1", decision_time="unused",
                trust_registry={}, provider_id="forged",
            )

    def test_signed_bytes_and_supplied_attestation_cannot_promote(self):
        with patch(
            "alpha_lab.research.phase2_archive_provenance.verify_signed_archive",
            return_value={"archive_id": "a", "sha256": "0" * 64},
        ):
            result = verify_archive_provenance(
                archive_path="unused", research_path="unused",
                manifest_path="unused", signature_path="unused",
                expected_archive_id="a", decision_time="unused",
                trust_registry={"provider": {"onboarding": "independently_verified",
                                             "ed25519_public_key": b"x" * 32}},
                provider_id="provider",
                attestation={"independently_verified": True, "capture_time": "2020-01-01"},
            )
        self.assertFalse(result["archive_provider_identity_independently_verified"])
        self.assertFalse(result["historical_capture_independently_attested"])
        self.assertFalse(result["eligible_for_strategy_promotion"])

    def test_archival_gate_rejects_caller_supplied_positive_claims(self):
        with patch(
            "alpha_lab.research.phase2_evidence_gate.verify_archival_availability",
            return_value={"archive_record_id": "a", "archive_sha256": "0" * 64,
                          "archive_provider": "p"},
        ), patch(
            "alpha_lab.research.phase2_evidence_gate.verify_archive_provenance",
            return_value={"archive_id": "a", "sha256": "0" * 64,
                          "historical_capture_independently_attested": True,
                          "eligible_for_strategy_promotion": True},
        ):
            result = evaluate_archived_research_evidence(
                availability={"decision_time": "t"},
                provenance={"decision_time": "t", "provider_id": "p"},
            )
        self.assertFalse(result["historical_capture_independently_attested"])
        self.assertFalse(result["eligible_for_strategy_promotion"])
        self.assertFalse(result["eligible_for_live_trading"])


if __name__ == "__main__":
    unittest.main()
