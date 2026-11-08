import unittest
from alpha_lab.research.fold_bootstrap import fold_aware_bootstrap, block_size_sensitivity

class FoldBootstrapTests(unittest.TestCase):
    def test_deterministic_repeated_run(self):
        folds = ((0.01, -0.005, 0.003, 0.002) * 10,
                 (-0.002, 0.006, 0.001, -0.001) * 10)
        a = fold_aware_bootstrap(folds, block_size=8, draws=200)
        b = fold_aware_bootstrap(folds, block_size=8, draws=200)
        self.assertEqual(a, b)
        self.assertEqual(a.boundary_crossings, 0)
        self.assertEqual(a.observations, 80)

    def test_constant_returns_have_exact_bound(self):
        result = fold_aware_bootstrap(((0.002,) * 20, (0.002,) * 30),
                                      draws=100, block_size=8)
        self.assertAlmostEqual(result.lower_confidence_bound, 0.002, places=12)

    def test_short_fold_rejected(self):
        with self.assertRaisesRegex(ValueError, "Fold shorter"):
            fold_aware_bootstrap(((0.01,) * 4, (0.01,) * 40), block_size=8)

    def test_nonfinite_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid period"):
            fold_aware_bootstrap(((float("nan"),) * 12,), block_size=8)

    def test_invalid_draws_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid bootstrap"):
            fold_aware_bootstrap(((0.01,) * 20,), draws=99)


    def test_sensitivity_reports_every_predeclared_block_size(self):
        folds = ((0.001,) * 40, (0.001,) * 40)
        result = block_size_sensitivity(folds, draws=100)
        self.assertEqual(set(result["bounds_by_block_size"]), {"4", "8", "16"})
        self.assertTrue(result["all_lower_bounds_positive"])
        self.assertFalse(result["promotion_authorised"])

    def test_sensitivity_rejects_infeasible_block_size(self):
        with self.assertRaisesRegex(ValueError, "Fold shorter"):
            block_size_sensitivity(((0.001,) * 10,), draws=100)

    def test_sensitivity_rejects_duplicate_block_size(self):
        with self.assertRaisesRegex(ValueError, "Invalid block"):
            block_size_sensitivity(((0.001,) * 40,), block_sizes=(4, 4), draws=100)

if __name__ == "__main__":
    unittest.main()
