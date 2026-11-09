"""Adversarial synthetic multi-asset P&L and fail-closed ledger regression."""
import unittest
from decimal import Decimal
from alpha_lab.research.pnl_reporting import report_pnl


class AdversarialPnlTests(unittest.TestCase):
    def test_two_assets_independent_cost_basis(self):
        orders = [
            {"symbol": "BTC", "side": "BUY", "quantity": "2", "price": "100",
             "fee": "2", "cash_delta": "-202"},
            {"symbol": "ETH", "side": "BUY", "quantity": "1", "price": "50",
             "fee": "1", "cash_delta": "-51"},
            {"symbol": "BTC", "side": "SELL", "quantity": "1", "price": "120",
             "fee": "1", "cash_delta": "119"},
        ]
        result = report_pnl(orders, {"BTC": "110", "ETH": "45"},
                            starting_cash="1000", liquidation_bps="100")
        # Cash 866; liquidation 110*.99 + 45*.99 = 153.45; NAV 1019.45.
        self.assertEqual(Decimal(result["realised_gross_pnl"]), Decimal("20"))
        self.assertEqual(Decimal(result["realised_net_pnl"]), Decimal("18"))
        self.assertEqual(Decimal(result["unrealised_gross_pnl"]), Decimal("5"))
        self.assertEqual(Decimal(result["unrealised_net_pnl"]), Decimal("3"))
        self.assertEqual(Decimal(result["liquidation_haircut"]), Decimal("1.55"))
        self.assertEqual(Decimal(result["final_liquidation_nav"]), Decimal("1019.45"))
        self.assertEqual(Decimal(result["net_total_pnl_after_liquidation"]), Decimal("19.45"))

    def test_duplicate_fills_nonfinite_values_and_naked_sales_rejected(self):
        base = {"fill_id": "same", "symbol": "BTC", "side": "BUY",
                "quantity": "1", "price": "100", "fee": "1", "cash_delta": "-101"}
        cases = [
            ([base, dict(base)], "Duplicate fill"),
            ([{**base, "quantity": "NaN"}], "Nonfinite"),
            ([{**base, "fee": "-1"}], "Invalid execution"),
            ([{"symbol": "BTC", "side": "SELL", "quantity": "1",
               "price": "100", "fee": "0", "cash_delta": "100"}], "Naked sale"),
            ([{**base, "fee_currency": "BTC"}], "Fee currency"),
        ]
        for orders, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                report_pnl(orders, {"BTC": "100"}, starting_cash="1000")

    def test_no_spread_impact_attribution_claim(self):
        result = report_pnl([], {"BTC": "100"}, starting_cash="1000")
        self.assertEqual(result["mode"], "RESEARCH_ONLY")
        self.assertFalse(result["spread_vs_impact_separately_identifiable"])
        self.assertFalse(result["trading_enabled"])


if __name__ == "__main__":
    unittest.main()
