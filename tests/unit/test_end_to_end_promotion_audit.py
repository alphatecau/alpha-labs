"""Cross-entry-point fail-closed checks for offline research interfaces."""
import unittest
from alpha_lab.research.strategy_evidence_bridge import screen_research_report
from alpha_lab.research.promotion_authority import decide_strategy_promotion


class EndToEndPromotionAuditTests(unittest.TestCase):
    def test_strategy_bridge_forged_flags_do_not_enable_trading(self):
        report = {
            "trading_enabled": False, "promotion_authorised": True,
            "live_trading_authorised": True, "strategy_profitable_verified": True,
            "point_in_time_provenance_verified": True, "costs_modelled": True,
            "holdout_independently_sealed": True,
            "oos_period_net_returns": [0.01] * 60,
            "oos_fold_net_returns": [0.02] * 5,
            "oos_trade_count": 60, "additional_cost_per_period": 0.001,
        }
        result = screen_research_report(report)
        self.assertFalse(result["trading_enabled"])
        self.assertFalse(result["promotion_authorised"])
        self.assertFalse(result["live_trading_authorised"])

    def test_missing_observations_fail_closed(self):
        result = screen_research_report({"trading_enabled": False})
        self.assertFalse(result["trading_enabled"])
        self.assertFalse(result["promotion_authorised"])
        self.assertFalse(result["live_trading_authorised"])

    def test_caller_supplied_attestation_cannot_authorise(self):
        result = decide_strategy_promotion(
            assessment={"promotion_authorised": True},
            archive_evidence={"historical_capture_independently_attested": True,
                              "eligible_for_strategy_promotion": True})
        self.assertFalse(result["promotion_authorised"])
        self.assertFalse(result["live_trading_authorised"])


if __name__ == "__main__":
    unittest.main()
