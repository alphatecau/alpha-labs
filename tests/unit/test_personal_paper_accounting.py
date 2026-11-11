"""Independent FIFO P&L oracle for simulated-only fills."""
import unittest
from decimal import Decimal

from alpha_lab.research.paper_accounting import reconcile_paper_pnl
from alpha_lab.research.paper_simulator import PaperLedger


class PersonalPaperAccountingTests(unittest.TestCase):
    def test_fifo_partial_sale_fees_and_nav(self):
        ledger = PaperLedger("1000")
        ledger.enable_simulation(operator_approved=True)
        ledger.fill(symbol="BTC", side="BUY", quantity="2",
                    reference_mid="100", executed_price="101", fee="1")
        ledger.fill(symbol="BTC", side="SELL", quantity="0.5",
                    reference_mid="110", executed_price="109", fee="0.5")
        result = reconcile_paper_pnl(ledger.fills, {"BTC": "110"}, starting_cash="1000")
        self.assertEqual(result["cash"], Decimal("851"))
        self.assertEqual(result["nav"], Decimal("1016"))
        self.assertEqual(result["realised"], Decimal("3.75"))
        self.assertEqual(result["unrealised"], Decimal("12.25"))
        self.assertEqual(result["fees"], Decimal("1.5"))
        self.assertEqual(result["nav"], ledger.nav({"BTC": "110"}))

    def test_multiple_fifo_lots_and_closed_position(self):
        ledger = PaperLedger("1000")
        ledger.enable_simulation(operator_approved=True)
        ledger.fill(symbol="BTC", side="BUY", quantity="1",
                    reference_mid="100", executed_price="100", fee="1")
        ledger.fill(symbol="BTC", side="BUY", quantity="1",
                    reference_mid="120", executed_price="120", fee="1")
        ledger.fill(symbol="BTC", side="SELL", quantity="2",
                    reference_mid="130", executed_price="130", fee="2")
        result = reconcile_paper_pnl(ledger.fills, {}, starting_cash="1000")
        self.assertEqual(result["realised"], Decimal("36"))
        self.assertEqual(result["unrealised"], Decimal("0"))
        self.assertEqual(result["nav"], Decimal("1036"))
        self.assertEqual(result["nav"], ledger.nav({}))

    def test_missing_mark_and_naked_sale_fail_closed(self):
        ledger = PaperLedger("1000")
        ledger.enable_simulation(operator_approved=True)
        ledger.fill(symbol="BTC", side="BUY", quantity="1",
                    reference_mid="100", executed_price="100", fee="0")
        with self.assertRaisesRegex(ValueError, "missing closing mark"):
            reconcile_paper_pnl(ledger.fills, {}, starting_cash="1000")
        bad = [{"symbol":"BTC","side":"SELL","quantity":"1","price":"100","fee":"0"}]
        with self.assertRaisesRegex(ValueError, "naked paper sale"):
            reconcile_paper_pnl(bad, {}, starting_cash="1000")


if __name__ == "__main__":
    unittest.main()
