"""Adversarial compatibility checks for merged OOS screen and Phase 1 bridge.

These tests do not certify data provenance or strategy profitability.
"""
import unittest

from alpha_lab.research.strategy_evidence_bridge import screen_research_report
from alpha_lab.strategy_evidence import evaluate_oos, ValidationConfig


class IntegrationEvidenceSafetyTests(unittest.TestCase):
    def test_aggregate_only_report_fails_closed(self):
        result = screen_research_report({"trading_enabled": False, "net_return": 999})
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(result["trading_enabled"])

    def test_missing_independent_provenance_fails_closed(self):
        report = {
            "trading_enabled": False,
            "oos_period_net_returns": [0.01] * 120,
            "oos_fold_net_returns": [0.01] * 5,
            "oos_trade_count": 40,
            "additional_cost_per_period": 0.001,
        }
        result = screen_research_report(report)
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("holdout_independently_sealed", result["missing_fields"])

    def test_cost_stress_rejects_unprofitable_returns(self):
        result = evaluate_oos(
            tuple([0.0001] * 120),
            trades=40,
            fold_net_returns=tuple([0.001] * 5),
            additional_cost_per_period=0.001,
            config=ValidationConfig(bootstrap_draws=100),
        )
        self.assertEqual(result.status, "REJECT")
        self.assertIn("NONPOSITIVE_COST_STRESS", result.reasons)

    def test_invalid_returns_cannot_be_screened(self):
        with self.assertRaises(ValueError):
            evaluate_oos(
                tuple([0.01] * 119 + [float("nan")]),
                trades=40,
                fold_net_returns=(0.01,) * 5,
                additional_cost_per_period=0,
            )


if __name__ == "__main__":
    unittest.main()
