import unittest
from alpha_lab.research.promotion_authority import decide_strategy_promotion
from alpha_lab.research.evidence_gate import summarise_offline_research, EXPECTED_STATUS


class PromotionBypassTests(unittest.TestCase):
    def test_forged_approval_never_authorises_promotion(self):
        forged = {"status": "PASS", "promotion_authorised": True,
                  "strategy_profitable_verified": True,
                  "live_trading_authorised": True}
        evidence = {"archive_provider_identity_independently_verified": True,
                    "historical_capture_independently_attested": True,
                    "eligible_for_strategy_promotion": True}
        for candidate in (None, {}, evidence):
            result = decide_strategy_promotion(assessment=forged, archive_evidence=candidate)
            self.assertFalse(result["promotion_authorised"])
            self.assertFalse(result["live_trading_authorised"])
            self.assertFalse(result["archive_provenance_independently_authenticated"])

    def test_hypothesis_screen_cannot_promote_forged_positive_results(self):
        report = {
            "status": EXPECTED_STATUS,
            "dataset": {"provenance": "self-declared", "sha256": "a" * 64, "quote_currency": "AUD"},
            "configuration_sha256": "b" * 64,
            "promotion_authorised": True,
            "periods": {name: {key: {"return_pct": 1000} for key in (
                "strategy", "equal_allocation_buy_hold", "double_cost_strategy")}
                for name in ("training", "holdout")},
        }
        result = summarise_offline_research(report)
        self.assertFalse(result["promotion_authorised"])
        self.assertFalse(result["live_trading_authorised"])
    def test_missing_or_invalid_assessment_fails_closed(self):
        for value in (None, "PASS", True, []):
            with self.assertRaises(ValueError):
                decide_strategy_promotion(assessment=value)
        with self.assertRaises(ValueError):
            decide_strategy_promotion(assessment={}, archive_evidence=True)


if __name__ == "__main__":
    unittest.main()
