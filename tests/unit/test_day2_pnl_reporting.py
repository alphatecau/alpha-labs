"""Synthetic independent arithmetic oracles for research-only P&L reporting."""
import unittest
from decimal import Decimal
from alpha_lab.research.pnl_reporting import report_pnl


class PnlReportingTests(unittest.TestCase):
    def test_partial_sale_fee_allocation_and_liquidation(self):
        orders = [
            {"symbol": "BTC", "side": "BUY", "quantity": "2",
             "price": "100", "fee": "1", "cash_delta": "-201"},
            {"symbol": "BTC", "side": "SELL", "quantity": "0.5",
             "price": "120", "fee": "0.3", "cash_delta": "59.7"},
        ]
        result = report_pnl(orders, {"BTC": "110"}, starting_cash="1000",
                            liquidation_bps="25")
        expected = {
            "realised_gross_pnl": "10",
            "realised_net_pnl": "9.45",
            "unrealised_gross_pnl": "15",
            "unrealised_net_pnl": "14.25",
            "liquidation_haircut": "0.4125",
            "net_total_pnl_after_liquidation": "23.2875",
            "final_liquidation_nav": "1023.2875",
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(Decimal(result[key]), Decimal(value))
        self.assertTrue(result["reconciled"])
        self.assertFalse(result["trading_enabled"])

    def test_full_exit_loss_and_zero_inventory(self):
        orders = [
            {"symbol": "ETH", "side": "BUY", "quantity": "2",
             "price": "50", "fee": "0.2", "cash_delta": "-100.2"},
            {"symbol": "ETH", "side": "SELL", "quantity": "2",
             "price": "40", "fee": "0.2", "cash_delta": "79.8"},
        ]
        result = report_pnl(orders, {"ETH": "40"}, starting_cash="1000")
        self.assertEqual(Decimal(result["realised_gross_pnl"]), Decimal("-20"))
        self.assertEqual(Decimal(result["realised_net_pnl"]), Decimal("-20.4"))
        self.assertEqual(Decimal(result["unrealised_net_pnl"]), Decimal("0"))
        self.assertEqual(Decimal(result["final_liquidation_nav"]), Decimal("979.6"))

    def test_multiple_lots_weighted_average_and_repeated_sale(self):
        orders = [
            {"symbol": "BTC", "side": "BUY", "quantity": "1",
             "price": "100", "fee": "1", "cash_delta": "-101"},
            {"symbol": "BTC", "side": "BUY", "quantity": "1",
             "price": "120", "fee": "1", "cash_delta": "-121"},
            {"symbol": "BTC", "side": "SELL", "quantity": "1",
             "price": "130", "fee": "1", "cash_delta": "129"},
        ]
        result = report_pnl(orders, {"BTC": "115"}, starting_cash="1000")
        self.assertEqual(Decimal(result["realised_gross_pnl"]), Decimal("20"))
        self.assertEqual(Decimal(result["realised_net_pnl"]), Decimal("18"))
        self.assertEqual(Decimal(result["unrealised_gross_pnl"]), Decimal("5"))
        self.assertEqual(Decimal(result["unrealised_net_pnl"]), Decimal("4"))
        self.assertEqual(Decimal(result["final_liquidation_nav"]), Decimal("1022"))

    def test_zero_trades_and_reject_tampering(self):
        result = report_pnl([], {"BTC": "100"}, starting_cash="1000")
        self.assertEqual(Decimal(result["net_total_pnl_after_liquidation"]), Decimal("0"))
        with self.assertRaisesRegex(ValueError, "cash delta"):
            report_pnl([{"symbol": "BTC", "side": "BUY", "quantity": "1",
                         "price": "100", "fee": "1", "cash_delta": "-100"}],
                       {"BTC": "100"}, starting_cash="1000")


if __name__ == "__main__":
    unittest.main()
