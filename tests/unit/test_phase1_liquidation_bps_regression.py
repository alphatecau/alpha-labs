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


    def test_independent_oracle_sell_and_partial_position(self):
        orders = self.orders + [{
            "symbol": "BTC", "side": "SELL", "quantity": "0.5",
            "price": "120", "fee": "0.3", "cash_delta": "59.7",
        }]
        audit = reconstruct(orders, {"BTC": "110"}, starting_cash="1000", liquidation_bps="25")
        # cash=858.7, remaining 1.5 BTC valued at 164.5875
        self.assertEqual(Decimal(audit["cash"]), Decimal("858.7"))
        self.assertEqual(Decimal(audit["positions"]["BTC"]), Decimal("1.5"))
        self.assertEqual(Decimal(audit["fees"]), Decimal("1.3"))
        self.assertEqual(Decimal(audit["final_liquidation_nav"]), Decimal("1023.2875"))

    def test_reject_tampered_order_cash_delta(self):
        altered = [dict(self.orders[0], cash_delta="-200")]
        with self.assertRaisesRegex(ValueError, "cash delta"):
            reconstruct(altered, {"BTC": "110"}, starting_cash="1000")

    def test_reject_naked_sale(self):
        orders = [{"symbol": "BTC", "side": "SELL", "quantity": "1",
                   "price": "100", "fee": "0", "cash_delta": "100"}]
        with self.assertRaisesRegex(ValueError, "Naked sale"):
            reconstruct(orders, {"BTC": "100"}, starting_cash="1000")

    def test_reject_negative_cash(self):
        with self.assertRaisesRegex(ValueError, "Negative cash"):
            reconstruct(self.orders, {"BTC": "110"}, starting_cash="100")

    def test_reject_missing_closing_mark(self):
        with self.assertRaisesRegex(ValueError, "Unknown symbol"):
            reconstruct(self.orders, {}, starting_cash="1000")

    def test_reject_nonfinite_closing_mark(self):
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            reconstruct(self.orders, {"BTC": "Infinity"}, starting_cash="1000")


    def test_simulator_effective_exit_haircut_contract(self):
        # Simulator marks an open position with both exit slippage and exit fee.
        # The ledger accepts the equivalent effective haircut expressed in bps.
        for one_way_bps in ("10", "20", "40"):
            with self.subTest(one_way_bps=one_way_bps):
                rate = Decimal(one_way_bps) / Decimal("10000")
                effective_bps = Decimal("10000") * (1 - (1 - rate) ** 2)
                audit = reconstruct(
                    self.orders, {"BTC": "110"}, starting_cash="1000",
                    liquidation_bps=effective_bps,
                )
                oracle = Decimal("799") + Decimal("220") * (1 - rate) ** 2
                self.assertEqual(Decimal(audit["final_liquidation_nav"]), oracle)


if __name__ == "__main__":
    unittest.main()
