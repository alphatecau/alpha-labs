"""One-shot fill stream consistency for independent P&L reconstruction."""
import unittest
from alpha_lab.research.pnl_reporting import report_pnl


class OneShotFillTests(unittest.TestCase):
    def test_generator_matches_list(self):
        fills = [
            {"fill_id": "a", "symbol": "BTC", "side": "BUY", "quantity": "2",
             "price": "100", "fee": "1", "cash_delta": "-201"},
            {"fill_id": "b", "symbol": "BTC", "side": "SELL", "quantity": "0.5",
             "price": "120", "fee": "0.3", "cash_delta": "59.7"},
        ]
        kwargs = dict(starting_cash="1000", liquidation_bps="25", require_fill_ids=True)
        expected = report_pnl(fills, {"BTC": "110"}, **kwargs)
        observed = report_pnl((fill for fill in fills), {"BTC": "110"}, **kwargs)
        self.assertEqual(observed, expected)
        self.assertEqual(observed["final_liquidation_nav"], "1023.2875")

    def test_duplicate_id_generator_fails(self):
        fill = {"fill_id": "duplicate", "symbol": "BTC", "side": "BUY",
                "quantity": "1", "price": "100", "fee": "0", "cash_delta": "-100"}
        with self.assertRaisesRegex(ValueError, "Duplicate fill"):
            report_pnl((x for x in (fill, fill)), {"BTC": "100"},
                       require_fill_ids=True)


if __name__ == "__main__":
    unittest.main()
