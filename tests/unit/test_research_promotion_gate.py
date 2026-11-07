"""Regression checks for the fail-closed research evidence gate."""
import unittest
from tools.research_promotion_gate import evaluate, REQUIRED_EVIDENCE


def complete():
    return {
        "experiment_id": "synthetic-test-only",
        "evidence": {key: True for key in REQUIRED_EVIDENCE},
        "metrics": {
            "net_return": 0.1, "cost_stress_net_return": 0.04,
            "max_drawdown": 0.02, "adjusted_lower_bound": 0.001,
            "closed_trades": 45, "positive_forward_folds": 9,
            "total_forward_folds": 14,
        },
    }


class ResearchGateTests(unittest.TestCase):
    def test_complete_is_review_only(self):
        result = evaluate(complete())
        self.assertEqual(result["decision"], "ELIGIBLE_FOR_INDEPENDENT_REVIEW")
        self.assertFalse(result["live_trading_authorised"])

    def test_missing_evidence_blocks(self):
        data = complete()
        del data["evidence"]["prospective_evaluation"]
        self.assertEqual(evaluate(data)["decision"], "BLOCKED")

    def test_false_evidence_blocks(self):
        data = complete()
        data["evidence"]["execution_cost_calibration"] = False
        self.assertEqual(evaluate(data)["decision"], "BLOCKED")

    def test_failed_cost_stress_rejects(self):
        data = complete()
        data["metrics"]["cost_stress_net_return"] = -0.01
        self.assertEqual(evaluate(data)["decision"], "REJECT")

    def test_sparse_trades_rejects(self):
        data = complete()
        data["metrics"]["closed_trades"] = 27
        self.assertEqual(evaluate(data)["decision"], "REJECT")

    def test_weak_forward_folds_rejects(self):
        data = complete()
        data["metrics"]["positive_forward_folds"] = 5
        self.assertEqual(evaluate(data)["decision"], "REJECT")

    def test_nan_blocks(self):
        data = complete()
        data["metrics"]["net_return"] = float("nan")
        self.assertEqual(evaluate(data)["decision"], "BLOCKED")

    def test_boolean_metric_blocks(self):
        data = complete()
        data["metrics"]["closed_trades"] = True
        self.assertEqual(evaluate(data)["decision"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
