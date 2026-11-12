"""Independent synthetic P&L identity and cost attribution regression tests.

The existing phase1 ledger does not report realised/unrealised P&L; these tests
establish an independent oracle, not a claim of implemented P&L reporting.
"""
import unittest
from decimal import Decimal

from alpha_lab.research.phase1_accounting import reconstruct
from alpha_lab.research.phase1_evidence import execution_cost_bridge


class PnlIdentityOracleTests(unittest.TestCase):
    def test_partial_sale_realised_unrealised_and_fees(self):
        orders = [
            {"symbol": "BTC", "side": "BUY", "quantity": "2",
             "price": "100", "fee": "1", "cash_delta": "-201"},
            {"symbol": "BTC", "side": "SELL", "quantity": "0.5",
             "price": "120", "fee": "0.3", "cash_delta": "59.7"},
        ]
        audit = reconstruct(orders, {"BTC": "110"}, starting_cash="1000")
        realised_gross = Decimal("0.5") * (Decimal("120") - Decimal("100"))
        unrealised_gross = Decimal("1.5") * (Decimal("110") - Decimal("100"))
        fees = Decimal("1.3")
        pnl_net = realised_gross + unrealised_gross - fees
        self.assertEqual(realised_gross, Decimal("10"))
        self.assertEqual(unrealised_gross, Decimal("15"))
        self.assertEqual(pnl_net, Decimal("23.7"))
        self.assertEqual(Decimal(audit["final_liquidation_nav"]), Decimal("1000") + pnl_net)
        self.assertEqual(Decimal(audit["cash"]), Decimal("858.7"))

    def test_loss_and_flat_position_identity(self):
        orders = [
            {"symbol": "ETH", "side": "BUY", "quantity": "2",
             "price": "50", "fee": "0.2", "cash_delta": "-100.2"},
            {"symbol": "ETH", "side": "SELL", "quantity": "2",
             "price": "40", "fee": "0.2", "cash_delta": "79.8"},
        ]
        audit = reconstruct(orders, {"ETH": "40"}, starting_cash="1000")
        realised_gross = Decimal("2") * (Decimal("40") - Decimal("50"))
        unrealised_gross = Decimal("0")
        self.assertEqual(realised_gross, Decimal("-20"))
        self.assertEqual(Decimal(audit["fees"]), Decimal("0.4"))
        self.assertEqual(Decimal(audit["positions"]["ETH"]), Decimal("0"))
        self.assertEqual(Decimal(audit["final_liquidation_nav"]),
                         Decimal("1000") + realised_gross + unrealised_gross - Decimal("0.4"))

    def test_execution_shortfall_not_double_counted_as_explicit_fee(self):
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


if __name__ == "__main__":
    unittest.main()
