"""Strict fill identifier gate for research-only accounting."""
import unittest
from alpha_lab.research.phase1_accounting import reconstruct
from alpha_lab.research.pnl_reporting import report_pnl


class StrictFillIdentifierTests(unittest.TestCase):
    def setUp(self):
        self.fill = {"symbol": "BTC", "side": "BUY", "quantity": "1",
                     "price": "100", "fee": "1", "cash_delta": "-101"}

    def test_strict_rejects_missing_identifier(self):
        with self.assertRaisesRegex(ValueError, "Missing required fill"):
            reconstruct([self.fill], {"BTC": "100"}, require_fill_ids=True)
        with self.assertRaisesRegex(ValueError, "Missing required fill"):
            report_pnl([self.fill], {"BTC": "100"}, require_fill_ids=True)

    def test_strict_accepts_unique_identifier(self):
        fill = {**self.fill, "fill_id": "synthetic-001"}
        self.assertTrue(reconstruct([fill], {"BTC": "100"},
                                    require_fill_ids=True)["reconciled"])
        self.assertTrue(report_pnl([fill], {"BTC": "100"},
                                   require_fill_ids=True)["reconciled"])

    def test_strict_rejects_duplicate_identifier(self):
        fill = {**self.fill, "fill_id": "synthetic-001"}
        with self.assertRaisesRegex(ValueError, "Duplicate fill"):
            report_pnl([fill, fill], {"BTC": "100"}, require_fill_ids=True)


if __name__ == "__main__":
    unittest.main()
