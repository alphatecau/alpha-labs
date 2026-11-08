"""Independent arithmetic fixtures for liquidation cost basis-point conversion."""
import unittest
from decimal import Decimal
from alpha_lab.research.phase1_accounting import reconstruct, reconcile_simulation


class LiquidationBpsRegressionTests(unittest.TestCase):
    def setUp(self):
        self.orders = [{
            "symbol": "BTC", "side": "BUY", "quantity": "2",
            "price": "100", "fee": "1", "cash_delta": "-201",
        }]

    def test_twenty_five_basis_points(self):
        audit = reconstruct(self.orders, {"BTC": "110"}, starting_cash="1000", liquidation_bps="25")
        # cash=799, marked value=220, liquidation fee=0.55
        self.assertEqual(Decimal(audit["final_liquidation_nav"]), Decimal("1018.45"))

    def test_zero_basis_points(self):
        audit = reconstruct(self.orders, {"BTC": "110"}, starting_cash="1000", liquidation_bps="0")
        self.assertEqual(Decimal(audit["final_liquidation_nav"]), Decimal("1019"))

    def test_one_hundred_basis_points(self):
        audit = reconstruct(self.orders, {"BTC": "110"}, starting_cash="1000", liquidation_bps="100")
        self.assertEqual(Decimal(audit["final_liquidation_nav"]), Decimal("1016.8"))

    def test_invalid_rate_rejected(self):
        for rate in ("-1", "10000", "NaN"):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                reconstruct(self.orders, {"BTC": "110"}, starting_cash="1000", liquidation_bps=rate)

    def test_simulator_nav_mismatch_fails_closed(self):
        simulation = {"orders": self.orders, "final_cash": "9799",
                      "final_nav": "10019", "total_fees": "1"}
        with self.assertRaises(ValueError):
            reconcile_simulation(simulation, {"BTC": "110"}, liquidation_bps="25")


if __name__ == "__main__":
    unittest.main()
