"""Issue #16: edge-case accounting tests, research-only.

The current ledger is a long/cash, single-currency order ledger. These tests
verify what it supports; cross-currency fee conversion and cost-basis P&L
remain unsupported and must not be represented as certified.
"""
import unittest
from decimal import Decimal
from alpha_lab.research.phase1_accounting import reconstruct, reconcile_simulation


class AccountingEdgeCases(unittest.TestCase):
    def test_partial_fills_aggregate_to_single_execution(self):
        parts = [
            {"symbol":"BTC","side":"BUY","quantity":"0.3","price":"100",
             "fee":"0.03","cash_delta":"-30.03"},
            {"symbol":"BTC","side":"BUY","quantity":"0.7","price":"100",
             "fee":"0.07","cash_delta":"-70.07"},
            {"symbol":"BTC","side":"SELL","quantity":"0.4","price":"110",
             "fee":"0.044","cash_delta":"43.956"},
        ]
        result = reconstruct(parts, {"BTC":"120"}, starting_cash="1000",
                             liquidation_bps="25")
        self.assertEqual(Decimal(result["cash"]), Decimal("943.856"))
        self.assertEqual(Decimal(result["positions"]["BTC"]), Decimal("0.6"))
        self.assertEqual(Decimal(result["fees"]), Decimal("0.144"))
        self.assertEqual(Decimal(result["final_liquidation_nav"]), Decimal("1015.676"))

    def test_decimal_rounding_exactness(self):
        orders = [{"symbol":"ETH","side":"BUY","quantity":"0.1",
                   "price":"0.3","fee":"0.00003","cash_delta":"-0.03003"}]
        result = reconstruct(orders, {"ETH":"0.3"}, starting_cash="1")
        self.assertEqual(Decimal(result["cash"]), Decimal("0.96997"))
        self.assertEqual(Decimal(result["final_liquidation_nav"]), Decimal("0.99997"))

    def test_duplicate_fill_not_idempotently_rejected(self):
        # Document a real limitation: there is no fill identifier in this API.
        fill = {"symbol":"BTC","side":"BUY","quantity":"1","price":"10",
                "fee":"0","cash_delta":"-10"}
        result = reconstruct([fill, fill], {"BTC":"10"}, starting_cash="100")
        self.assertEqual(Decimal(result["positions"]["BTC"]), Decimal("2"))
        self.assertEqual(result["order_count"], 2)

    def test_fee_currency_is_not_a_supported_input(self):
        # Explicitly demonstrate that the current API ignores a foreign fee
        # currency field; this must be addressed before multi-currency use.
        fill = {"symbol":"BTC","side":"BUY","quantity":"1","price":"10",
                "fee":"1","fee_currency":"BNB","cash_delta":"-11"}
        result = reconstruct([fill], {"BTC":"10"}, starting_cash="100")
        self.assertEqual(Decimal(result["fees"]), Decimal("1"))
        self.assertNotIn("fee_currency", result)

    def test_simulation_reconciliation_rejects_forged_nav(self):
        simulation = {"orders":[], "final_cash":"10000",
                      "final_nav":"10001", "total_fees":"0"}
        with self.assertRaisesRegex(ValueError, "Final NAV mismatch"):
            reconcile_simulation(simulation, {"BTC":"100"}, liquidation_bps="0")


if __name__ == "__main__":
    unittest.main()
