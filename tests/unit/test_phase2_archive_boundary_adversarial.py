"""Adversarial archive consistency tests using mocked lower-level validators.

These tests do not authenticate an external provider or historical timestamp.
"""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from alpha_lab.research.phase2_evidence_gate import evaluate_archived_research_evidence


class ArchiveBoundaryNegativeTests(unittest.TestCase):
    def setUp(self):
        self.decision = datetime(2025, 1, 3, tzinfo=timezone.utc)
        self.availability = {"decision_time": self.decision}
        self.provenance = {"decision_time": self.decision, "provider_id": "provider-a"}
        self.chronological = {
            "archive_record_id": "archive-a",
            "archive_sha256": "a" * 64,
            "archive_provider": "provider-a",
        }
        self.verified = {"archive_id": "archive-a", "sha256": "a" * 64}

    def evaluate(self, *, availability=None, provenance=None, chronological=None, verified=None):
        with patch(
            "alpha_lab.research.phase2_evidence_gate.verify_archival_availability",
            return_value=self.chronological if chronological is None else chronological,
        ), patch(
            "alpha_lab.research.phase2_evidence_gate.verify_archive_provenance",
            return_value=self.verified if verified is None else verified,
        ):
            return evaluate_archived_research_evidence(
                availability=self.availability if availability is None else availability,
                provenance=self.provenance if provenance is None else provenance,
            )

    def test_consistent_claims_still_deny_promotion(self):
        result = self.evaluate()
        self.assertIs(result["eligible_for_strategy_promotion"], False)
        self.assertIs(result["eligible_for_live_trading"], False)
        self.assertIs(result["historical_capture_independently_attested"], False)

    def test_archive_identity_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            self.evaluate(verified={"archive_id": "forged", "sha256": "a" * 64})

    def test_archive_digest_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.evaluate(verified={"archive_id": "archive-a", "sha256": "b" * 64})

    def test_provider_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "provider identity mismatch"):
            self.evaluate(provenance={"decision_time": self.decision, "provider_id": "other"})

    def test_decision_timestamp_mismatch_rejected(self):
        other = datetime(2025, 1, 4, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "Decision time mismatch"):
            self.evaluate(provenance={"decision_time": other, "provider_id": "provider-a"})


if __name__ == "__main__":
    unittest.main()
