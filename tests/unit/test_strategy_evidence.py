import unittest
from dataclasses import replace
from alpha_lab.strategy_evidence import ValidationConfig, evaluate_oos

class StrategyEvidenceTests(unittest.TestCase):
    def run_screen(self, returns, *, trades=50, folds=(0.01, 0.02, 0.03, 0.04),
                   cost=0.0001, config=ValidationConfig()):
        return evaluate_oos(tuple(returns), trades=trades,
                            fold_net_returns=tuple(folds),
                            additional_cost_per_period=cost, config=config)

    def test_insufficient_trades_rejected(self):
        r = self.run_screen([0.002] * 150, trades=27)
        self.assertEqual(r.status, "REJECT")
        self.assertIn("INSUFFICIENT_TRADES", r.reasons)

    def test_negative_cost_stress_rejected(self):
        r = self.run_screen([0.0001] * 150, cost=0.001)
        self.assertIn("NONPOSITIVE_COST_STRESS", r.reasons)

    def test_negative_returns_fail_bootstrap(self):
        r = self.run_screen([-0.001] * 150, cost=0)
        self.assertIn("NONPOSITIVE_BOOTSTRAP_LOWER_BOUND", r.reasons)

    def test_replay_deterministic(self):
        a = self.run_screen([0.001 + (i % 3) * 0.0001 for i in range(150)])
        b = self.run_screen([0.001 + (i % 3) * 0.0001 for i in range(150)])
        self.assertEqual(a, b)

    def test_positive_fixture_never_automatically_promoted(self):
        r = self.run_screen([0.005] * 150)
        self.assertEqual(r.status, "REVIEW_REQUIRED")

    def test_too_few_folds_rejected(self):
        r = self.run_screen([0.005] * 150, folds=(0.01, 0.02))
        self.assertIn("INSUFFICIENT_FOLDS", r.reasons)

    def test_invalid_cost_rejected(self):
        with self.assertRaises(ValueError):
            self.run_screen([0.005] * 150, cost=-0.01)

    def test_impossible_loss_rejected(self):
        with self.assertRaises(ValueError):
            self.run_screen([0.005] * 149 + [-1.0])

    def test_block_exceeds_history_rejected(self):
        r = self.run_screen([0.005] * 10, config=replace(ValidationConfig(), block_size=11))
        self.assertIn("BLOCK_EXCEEDS_HISTORY", r.reasons)

    def test_max_drawdown(self):
        r = self.run_screen([0.1, -0.2, 0.1] * 50)
        self.assertGreater(r.max_drawdown, 0.19)

if __name__ == "__main__":
    unittest.main()
