import unittest
from alpha_lab.research.strategy_evidence_bridge import screen_research_report

class EvidenceBridgeTests(unittest.TestCase):
    def test_legacy_summary_requires_raw_observations(self):
        result = screen_research_report({"trading_enabled": False,
            "periods": {"training": {}, "holdout": {}}})
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("oos_period_net_returns", result["missing_fields"])
        self.assertFalse(result["trading_enabled"])

    def test_unsealed_holdout_is_not_screened(self):
        result = screen_research_report({
            "trading_enabled": False, "oos_period_net_returns": [0.01] * 150,
            "oos_fold_net_returns": [0.1] * 4, "oos_trade_count": 60,
            "additional_cost_per_period": 0.001,
            "point_in_time_provenance_verified": True, "costs_modelled": True,
            "holdout_independently_sealed": False})
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("holdout_independently_sealed", result["missing_fields"])

    def test_rejects_live_enabled_report(self):
        with self.assertRaises(ValueError):
            screen_research_report({"trading_enabled": True})

    def test_screen_never_approves_execution(self):
        result = screen_research_report({
            "trading_enabled": False, "oos_period_net_returns": [0.005] * 150,
            "oos_fold_net_returns": [0.1] * 4, "oos_trade_count": 60,
            "additional_cost_per_period": 0.001,
            "point_in_time_provenance_verified": True, "costs_modelled": True,
            "holdout_independently_sealed": True})
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertFalse(result["trading_enabled"])

if __name__ == "__main__":
    unittest.main()
