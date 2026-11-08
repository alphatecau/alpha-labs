"""Phase 2 adversarial regression tests: research promotion must fail closed.

These tests intentionally do not assert that archive signatures establish an
independently trusted provider or that any strategy is eligible for trading.
"""
import unittest

from alpha_lab.research.promotion_authority import decide_strategy_promotion
from alpha_lab.research.strategy_evidence_bridge import screen_research_report
from alpha_lab.research.phase2_evidence_gate import evaluate_archived_research_evidence


class Phase2FailClosedTests(unittest.TestCase):
    def test_authority_rejects_forged_positive_payloads(self):
        forged = {
            "promotion_authorised": True,
            "live_trading_authorised": True,
            "strategy_profitable_verified": True,
            "archive_provenance_independently_authenticated": True,
            "historical_capture_independently_attested": True,
            "status": "APPROVED",
        }
        for evidence in (None, {}, forged, {"eligible_for_strategy_promotion": True}):
            with self.subTest(evidence=evidence):
                decision = decide_strategy_promotion(
                    assessment=forged, archive_evidence=evidence
                )
                self.assertIs(decision["promotion_authorised"], False)
                self.assertIs(decision["live_trading_authorised"], False)
                self.assertIs(
                    decision["archive_provenance_independently_authenticated"], False
                )

    def test_bridge_denies_missing_or_forged_evidence(self):
        for payload in (
            {"trading_enabled": False},
            {"trading_enabled": False, "promotion_authorised": True,
             "live_trading_authorised": True},
            {"trading_enabled": False, "point_in_time_provenance_verified": True,
             "promotion_authorised": True},
        ):
            with self.subTest(payload=payload):
                result = screen_research_report(payload)
                self.assertIs(result["promotion_authorised"], False)
                self.assertIs(result["live_trading_authorised"], False)
                self.assertIs(result["trading_enabled"], False)

    def test_bridge_rejects_trading_enabled_input(self):
        with self.assertRaises(ValueError):
            screen_research_report({"trading_enabled": True})

    def test_archive_gate_rejects_missing_inputs(self):
        for availability, provenance in (
            (None, None),
            ({}, None),
            (None, {}),
            ("forged", {}),
            ({}, "forged"),
        ):
            with self.subTest(availability=availability, provenance=provenance):
                with self.assertRaises(ValueError):
                    evaluate_archived_research_evidence(
                        availability=availability, provenance=provenance
                    )

    def test_authority_rejects_invalid_archive_evidence_types(self):
        for evidence in (True, "verified", [], 1):
            with self.subTest(evidence=evidence):
                with self.assertRaises(ValueError):
                    decide_strategy_promotion(assessment={}, archive_evidence=evidence)


if __name__ == "__main__":
    unittest.main()
