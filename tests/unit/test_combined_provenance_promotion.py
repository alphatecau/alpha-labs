"""Combined post-merge regression: archive evidence cannot authorise promotion."""
import unittest

from alpha_lab.research.phase2_evidence_gate import evaluate_archived_research_evidence
from alpha_lab.research.promotion_authority import decide_strategy_promotion


class CombinedGateTests(unittest.TestCase):
    def test_missing_archive_evidence_never_promotes(self):
        assessment = {"status": "PASS", "promotion_authorised": True}
        for evidence in (None, {}, {"eligible_for_strategy_promotion": True,
                                    "historical_capture_independently_attested": True}):
            result = decide_strategy_promotion(assessment=assessment, archive_evidence=evidence)
            self.assertFalse(result["promotion_authorised"])
            self.assertFalse(result["live_trading_authorised"])

    def test_malformed_combined_gate_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            evaluate_archived_research_evidence(availability=None, provenance={})
        with self.assertRaises(ValueError):
            evaluate_archived_research_evidence(availability={}, provenance=None)
        with self.assertRaises(ValueError):
            decide_strategy_promotion(assessment={}, archive_evidence="verified")

    def test_archive_gate_and_promotion_authority_remain_separate(self):
        """Static guard: an asserted archive result cannot confer approval."""
        fake_archive = {
            "status": "EVIDENCE_CONSISTENT_PROVENANCE_UNVERIFIED",
            "eligible_for_strategy_promotion": True,
            "eligible_for_live_trading": True,
            "provider_identity_independently_authenticated": True,
            "historical_capture_independently_attested": True,
        }
        decision = decide_strategy_promotion(
            assessment={"promotion_authorised": True}, archive_evidence=fake_archive)
        self.assertFalse(decision["promotion_authorised"])
        self.assertFalse(decision["live_trading_authorised"])


if __name__ == "__main__":
    unittest.main()
