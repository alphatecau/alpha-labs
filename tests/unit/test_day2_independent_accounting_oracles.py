"""Day 2 independent decimal accounting oracles; synthetic research data only."""
import unittest
from decimal import Decimal

from alpha_lab.research.phase1_accounting import reconstruct, reconcile_simulation
from alpha_lab.research.phase1_evidence import execution_cost_bridge


class IndependentAccountingOracles(unittest.TestCase):
    def setUp(self):
        self.orders = [
            {"fill_id": "btc-buy", "symbol": "BTC", "side": "BUY",
             "quantity": "2", "price": "100", "fee": "1", "cash_delta": "-201"},
            {"fill_id": "eth-buy", "symbol": "ETH", "side": "BUY",
             "quantity": "1", "price": "50", "fee": "0.5", "cash_delta": "-50.5"},
            {"fill_id": "btc-partial-sell", "symbol": "BTC", "side": "SELL",
             "quantity": "0.5", "price": "120", "fee": "0.3", "cash_delta": "59.7"},
        ]
        self.marks = {"BTC": "110", "ETH": "45"}

    def test_multisymbol_partial_sale_and_liquidation_oracle(self):
        audit = reconstruct(self.orders, self.marks, starting_cash="1000", liquidation_bps="25")
        self.assertEqual(Decimal(audit["cash"]), Decimal("808.2"))
        self.assertEqual(Decimal(audit["positions"]["BTC"]), Decimal("1.5"))
        self.assertEqual(Decimal(audit["positions"]["ETH"]), Decimal("1"))
        self.assertEqual(Decimal(audit["fees"]), Decimal("1.8"))
        self.assertEqual(Decimal(audit["gross_executed_notional"]), Decimal("310"))
        self.assertEqual(Decimal(audit["final_liquidation_nav"]), Decimal("1017.675"))
        self.assertEqual(audit["order_count"], 3)

    def test_zero_trade_oracle(self):
        audit = reconstruct([], {"BTC": "100"}, starting_cash="1000", liquidation_bps="25")
        self.assertEqual(Decimal(audit["final_liquidation_nav"]), Decimal("1000"))
        self.assertEqual(Decimal(audit["fees"]), Decimal("0"))

    def test_simulation_reconciliation_and_tampering(self):
        valid = {"orders": self.orders, "final_cash": "9808.2",
                 "final_nav": "10017.675", "total_fees": "1.8"}
        self.assertTrue(reconcile_simulation(valid, self.marks, liquidation_bps="25")["reconciled"])
        for key, bad in (("final_cash", "9808.3"), ("final_nav", "10017.676"),
                         ("total_fees", "1.9")):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "mismatch"):
                reconcile_simulation({**valid, key: bad}, self.marks, liquidation_bps="25")

    def test_duplicate_fill_id_and_unsupported_fee_currency_rejected(self):
        duplicate = [self.orders[0], {**self.orders[1], "fill_id": "btc-buy"}]
        with self.assertRaisesRegex(ValueError, "Duplicate fill"):
            reconstruct(duplicate, self.marks, starting_cash="1000")
        with self.assertRaisesRegex(ValueError, "Fee currency"):
            reconstruct([{**self.orders[0], "fee_currency": "BTC"}],
                        self.marks, starting_cash="1000")

    def test_execution_shortfall_independent_oracle(self):
        fills = [
            {"side": "BUY", "quantity": "2", "reference_mid": "100",
             "executed_price": "101", "fee": "0.5"},
            {"side": "SELL", "quantity": "1", "reference_mid": "110",
             "executed_price": "109", "fee": "0.25"},
        ]
        result = execution_cost_bridge(fills)
        self.assertEqual(Decimal(result["explicit_fees"]), Decimal("0.75"))
        self.assertEqual(Decimal(result["execution_shortfall_vs_mid"]), Decimal("3"))
        self.assertEqual(Decimal(result["combined_cost"]), Decimal("3.75"))
        self.assertFalse(result["spread_vs_impact_separately_identifiable"])

    def test_invalid_marks_and_cash_delta_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "cash delta"):
            reconstruct([{**self.orders[0], "cash_delta": "-200"}],
                        self.marks, starting_cash="1000")
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            reconstruct(self.orders, {"BTC": "NaN", "ETH": "45"},
                        starting_cash="1000")
        with self.assertRaisesRegex(ValueError, "Unknown symbol"):
            reconstruct(self.orders, {"BTC": "110"}, starting_cash="1000")


if __name__ == "__main__":
    unittest.main()
