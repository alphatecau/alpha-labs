"""Determinism and future-data isolation tests."""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from alpha_lab.data.csv_import import Bar, Dataset
from alpha_lab.research.walk_forward import evaluate_windows


class WalkForwardTests(unittest.TestCase):
    def dataset(self, count=1100, alter_future=False):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        bars = []

        for i in range(count):
            price = Decimal(100 + (i % 30))

            if alter_future and i >= 888:
                price += Decimal(50)

            bars.append(Bar(
                start + timedelta(hours=i),
                price, price, price, price, Decimal(1)
            ))

        return Dataset(
            tuple(bars), "USDT", "test-hash",
            "synthetic-test", 60
        )

    def test_deterministic(self):
        data = self.dataset()
        self.assertEqual(
            evaluate_windows(data),
            evaluate_windows(data)
        )

    def test_future_candles_do_not_change_first_window(self):
        original = evaluate_windows(self.dataset())
        altered = evaluate_windows(
            self.dataset(alter_future=True)
        )

        self.assertEqual(
            original["folds"][0],
            altered["folds"][0]
        )

    def test_insufficient_history_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_windows(self.dataset(800))

    def test_research_only(self):
        result = evaluate_windows(self.dataset())
        self.assertFalse(result["trading_enabled"])
        self.assertEqual(result["total_windows"], 2)
        self.assertEqual(result["quote_currency"], "USDT")


if __name__ == "__main__":
    unittest.main()
