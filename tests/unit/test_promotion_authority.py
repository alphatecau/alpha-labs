import unittest
from alpha_lab.research.promotion_authority import decide_strategy_promotion


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

    def test_missing_or_invalid_assessment_fails_closed(self):
        for value in (None, "PASS", True, []):
            with self.assertRaises(ValueError):
                decide_strategy_promotion(assessment=value)
        with self.assertRaises(ValueError):
            decide_strategy_promotion(assessment={}, archive_evidence=True)


if __name__ == "__main__":
    unittest.main()
