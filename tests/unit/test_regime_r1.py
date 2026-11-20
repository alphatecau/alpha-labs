import unittest
from decimal import Decimal
from alpha_lab.research.strategies.regime_r1 import r1_signal

class RegimeR1Tests(unittest.TestCase):
    def test_warmup_and_flat_prices(self):
        prices = [Decimal("100")] * 800
        self.assertEqual(r1_signal(prices), [False] * len(prices))

    def test_future_changes_cannot_modify_prior_signal(self):
        prices = [Decimal("100") + Decimal(i) / 100 for i in range(820)]
        a = r1_signal(prices)
        prices[-1] = Decimal("999")
        b = r1_signal(prices)
        self.assertEqual(a[:-1], b[:-1])

    def test_insufficient_history_stays_flat(self):
        self.assertEqual(r1_signal([Decimal("100")] * 768), [False] * 768)

    def test_nonpositive_rejected(self):
        with self.assertRaises(ValueError):
            r1_signal([Decimal("1"), Decimal("0")])
