"""Independent deterministic accounting identities, no market data claims."""
import unittest
from decimal import Decimal
from alpha_lab.research.pnl_reporting import report_pnl


class AccountingProperties(unittest.TestCase):
    def test_many_partial_sales_conserve_nav_and_pnl(self):
        for sold_units in range(1, 10):
            with self.subTest(sold_units=sold_units):
                fills = [{"fill_id": "buy", "symbol": "BTC", "side": "BUY",
                          "quantity": "10", "price": "10", "fee": "1",
                          "cash_delta": "-101"}]
                for i in range(sold_units):
                    fills.append({"fill_id": f"sell-{i}", "symbol": "BTC",
                                  "side": "SELL", "quantity": "1",
                                  "price": "12", "fee": "0.1",
                                  "cash_delta": "11.9"})
                report = report_pnl(fills, {"BTC": "11"}, starting_cash="1000",
                                    liquidation_bps="10", require_fill_ids=True)
                nav = Decimal(report["final_liquidation_nav"])
                pnl = Decimal(report["net_total_pnl_after_liquidation"])
                self.assertLessEqual(abs(nav - Decimal("1000") - pnl),
                                     Decimal("0.000000000001"))
                self.assertEqual(report["cost_basis_method"], "WEIGHTED_AVERAGE")
                self.assertFalse(report["trading_enabled"])

    def test_multisymbol_ledger_conservation(self):
        fills = [
            {"fill_id": "btc", "symbol": "BTC", "side": "BUY",
             "quantity": "1", "price": "100", "fee": "1", "cash_delta": "-101"},
            {"fill_id": "eth", "symbol": "ETH", "side": "BUY",
             "quantity": "2", "price": "50", "fee": "2", "cash_delta": "-102"},
        ]
        report = report_pnl(fills, {"BTC": "110", "ETH": "55"},
                            starting_cash="1000", require_fill_ids=True)
        self.assertEqual(Decimal(report["final_liquidation_nav"]), Decimal("1017"))
        self.assertEqual(Decimal(report["net_total_pnl_after_liquidation"]),
                         Decimal("17"))


if __name__ == "__main__":
    unittest.main()
