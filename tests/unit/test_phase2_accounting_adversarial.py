"""Adversarial research accounting invariants; no claim of market profitability."""
import unittest

from alpha_lab.research.phase1_accounting import reconstruct, reconcile_simulation


class AccountingAdversarialTests(unittest.TestCase):
    def test_cash_and_liquidation_nav_reconstructed_independently(self):
        orders = [
            {"symbol": "BTC", "side": "BUY", "quantity": "1", "price": "100",
             "fee": "1", "cash_delta": "-101"},
            {"symbol": "BTC", "side": "SELL", "quantity": "0.5", "price": "110",
             "fee": "0.5", "cash_delta": "54.5"},
        ]
        result = reconstruct(orders, {"BTC": "120"}, starting_cash="1000")
        self.assertEqual(result["cash"], "953.5")
        self.assertEqual(result["final_liquidation_nav"], "1013.5")
        self.assertEqual(result["fees"], "1.5")
        self.assertTrue(result["reconciled"])

    def test_forged_cash_delta_rejected(self):
        order = {"symbol": "BTC", "side": "BUY", "quantity": "1",
                 "price": "100", "fee": "1", "cash_delta": "-100"}
        with self.assertRaisesRegex(ValueError, "cash delta"):
            reconstruct([order], {"BTC": "100"})

    def test_naked_sale_rejected(self):
        order = {"symbol": "BTC", "side": "SELL", "quantity": "1",
                 "price": "100", "fee": "1", "cash_delta": "99"}
        with self.assertRaisesRegex(ValueError, "Naked sale"):
            reconstruct([order], {"BTC": "100"})

    def test_nonfinite_price_rejected(self):
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            reconstruct([], {"BTC": "NaN"})

    def test_forged_simulation_nav_rejected(self):
        simulation = {
            "orders": [],
            "final_cash": "10000",
            "final_nav": "10001",
            "total_fees": "0",
        }
        with self.assertRaisesRegex(ValueError, "Final NAV mismatch"):
            reconcile_simulation(simulation, {"BTC": "100"}, liquidation_bps="0")


if __name__ == "__main__":
    unittest.main()
