"""Step 3: independent decimal order ledger with explicit cost sensitivity."""
import unittest
from decimal import Decimal

from alpha_lab.research.phase1_accounting import reconstruct, reconcile_simulation


class IndependentCostNavTests(unittest.TestCase):
    def test_cash_position_fee_and_nav_oracle(self):
        orders = [
            {"symbol": "BTC", "side": "BUY", "quantity": "2",
             "price": "100", "fee": "2", "cash_delta": "-202"},
            {"symbol": "BTC", "side": "SELL", "quantity": "1",
             "price": "110", "fee": "1.1", "cash_delta": "108.9"},
        ]
        result = reconstruct(orders, {"BTC": "120"},
                             starting_cash="1000", liquidation_bps="25")
        self.assertEqual(Decimal(result["cash"]), Decimal("906.9"))
        self.assertEqual(Decimal(result["fees"]), Decimal("3.1"))
        self.assertEqual(Decimal(result["positions"]["BTC"]), Decimal("1"))
        self.assertEqual(Decimal(result["final_liquidation_nav"]), Decimal("1026.6"))

    def test_liquidation_cost_monotonicity(self):
        orders = [{"symbol": "BTC", "side": "BUY", "quantity": "1",
                   "price": "100", "fee": "1", "cash_delta": "-101"}]
        low = reconstruct(orders, {"BTC": "120"},
                          starting_cash="1000", liquidation_bps="0")
        high = reconstruct(orders, {"BTC": "120"},
                           starting_cash="1000", liquidation_bps="100")
        self.assertEqual(Decimal(low["final_liquidation_nav"]) -
                         Decimal(high["final_liquidation_nav"]), Decimal("1.2"))

    def test_forged_fee_and_nav_rejected(self):
        simulation = {"orders": [], "final_cash": "10000",
                      "final_nav": "10000", "total_fees": "1"}
        with self.assertRaisesRegex(ValueError, "Fee mismatch"):
            reconcile_simulation(simulation, {"BTC": "100"}, liquidation_bps="0")

    def test_negative_cash_and_overfill_rejected(self):
        orders = [{"symbol": "BTC", "side": "BUY", "quantity": "2",
                   "price": "100", "fee": "0", "cash_delta": "-200"}]
        with self.assertRaisesRegex(ValueError, "Negative cash"):
            reconstruct(orders, {"BTC": "100"}, starting_cash="100")


if __name__ == "__main__":
    unittest.main()
