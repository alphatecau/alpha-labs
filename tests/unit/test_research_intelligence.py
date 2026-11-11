import unittest
from alpha_lab.research.regimes import classify_regime
from alpha_lab.research.robustness import stress_costs
from alpha_lab.research.daily_review import review_events

class ResearchIntelligenceTests(unittest.TestCase):
    def test_unknown_short_history(self):
        self.assertEqual(classify_regime([100, 101]).regime, "UNKNOWN")

    def test_crash_precedence(self):
        self.assertEqual(classify_regime([100] * 20 + [80]).regime, "CRASH")

    def test_causal_trailing_window(self):
        values = [100] * 21
        self.assertEqual(classify_regime([999] + values).regime, classify_regime(values).regime)

    def test_invalid_prices_fail_closed(self):
        with self.assertRaises(ValueError):
            classify_regime([100] * 20 + [float("nan")])

    def test_cost_sensitivity_rejects(self):
        result = stress_costs([0.005] * 40)
        self.assertEqual(result.verdict, "REJECT")

    def test_low_sample_rejects(self):
        self.assertEqual(stress_costs([0.1] * 10).verdict, "REJECT")

    def test_positive_is_not_approval(self):
        self.assertEqual(stress_costs([0.05] * 40).verdict, "REVIEW_ONLY")

    def test_daily_review_flags_failure(self):
        result = review_events([{"type": "data", "status": "stale"}])
        self.assertEqual(result.verdict, "REVIEW_REQUIRED")

    def test_daily_review_empty(self):
        self.assertEqual(review_events([]).verdict, "INSUFFICIENT_DATA")

    def test_malformed_event_halts(self):
        self.assertEqual(review_events([{"type": "trade"}]).verdict, "HALT_REVIEW")

if __name__ == "__main__":
    unittest.main()
