import unittest
from datetime import date
from alpha_lab.research.phase1_split_reconciliation import reconcile_split_adjusted_close


class SplitReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.a = date(2025, 1, 2)
        self.b = date(2025, 1, 3)
        self.kw = dict(raw_closes={self.a: "100", self.b: "50"},
                       adjusted_closes={self.a: "50", self.b: "50"},
                       split_factors={self.a: "1", self.b: "2"},
                       cash_dividends={self.a: "0", self.b: "0"})

    def test_split_only_oracle(self):
        result = reconcile_split_adjusted_close(**self.kw)
        self.assertEqual(result["status"], "SPLIT_ARITHMETIC_CONSISTENT_NOT_AUTHENTICATED")
        self.assertFalse(result["eligible_for_strategy_promotion"])

    def test_bad_adjustment_rejected(self):
        with self.assertRaisesRegex(ValueError, "mismatch"):
            reconcile_split_adjusted_close(**dict(self.kw, adjusted_closes={self.a: "100", self.b: "50"}))

    def test_dividend_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Dividend"):
            reconcile_split_adjusted_close(**dict(self.kw, cash_dividends={self.a: "0", self.b: "1"}))

    def test_missing_date_rejected(self):
        with self.assertRaisesRegex(ValueError, "date coverage"):
            reconcile_split_adjusted_close(**dict(self.kw, adjusted_closes={self.a: "50"}))

    def test_nonfinite_and_invalid_split_rejected(self):
        for value in ("NaN", "Infinity", "0", "-2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                reconcile_split_adjusted_close(**dict(self.kw, split_factors={self.a: "1", self.b: value}))


if __name__ == "__main__":
    unittest.main()
