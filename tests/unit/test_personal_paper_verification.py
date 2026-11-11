"""Independent deterministic accounting and fail-closed paper risk regression tests.

Offline only. No network, broker, keys, live trading, or database migrations.
"""
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from alpha_lab.research.paper_simulator import PaperLedger
from alpha_lab.research.paper_risk import authorise_simulated_order
from alpha_lab.research.paper_runtime import PaperRuntime


class PersonalPaperVerification(unittest.TestCase):
    def test_independent_cash_nav_and_fees_oracle(self):
        ledger = PaperLedger("1000")
        ledger.enable_simulation(operator_approved=True)
        buy = ledger.fill(symbol="BTC", side="BUY", quantity="2",
                          reference_mid="100", executed_price="101", fee="1")
        sell = ledger.fill(symbol="BTC", side="SELL", quantity="0.5",
                           reference_mid="110", executed_price="109", fee="0.5")
        self.assertEqual(ledger.cash, Decimal("851"))
        self.assertEqual(ledger.positions["BTC"], Decimal("1.5"))
        self.assertEqual(ledger.nav({"BTC": "110"}), Decimal("1016"))
        self.assertEqual(Decimal(buy["cash_delta"]), Decimal("-203"))
        self.assertEqual(Decimal(sell["cash_delta"]), Decimal("54"))
        self.assertEqual(Decimal(buy["shortfall_vs_mid"]), Decimal("2"))
        self.assertEqual(Decimal(sell["shortfall_vs_mid"]), Decimal("0.5"))
        self.assertEqual(ledger.sequence, 2)
        self.assertEqual(sell["previous_hash"], buy["audit_hash"])

    def test_risk_boundaries_and_halt(self):
        args = dict(nav="1000", initial_nav="1000", peak_nav="1000",
                    day_start_nav="1000", proposed_loss="2.5",
                    aggregate_open_risk="7.5", gross_notional="800",
                    proposed_notional="200", data_fresh=True,
                    ledger_reconciled=True, operator_enabled=True)
        self.assertTrue(authorise_simulated_order(**args)["approved"])
        for changes, expected in [
            ({"proposed_loss": "2.51"}, "position risk exceeded"),
            ({"aggregate_open_risk": "7.51"}, "aggregate risk exceeded"),
            ({"gross_notional": "801"}, "gross notional exceeded"),
            ({"data_fresh": False}, "stale or unverified market data"),
            ({"operator_enabled": False}, "operator HALT"),
            ({"ledger_reconciled": False}, "unreconciled ledger"),
        ]:
            decision = authorise_simulated_order(**(args | changes))
            self.assertFalse(decision["approved"])
            self.assertIn(expected, decision["reasons"])
            self.assertFalse(decision["live_execution_authorised"])

    def test_runtime_restart_requires_new_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "paper.sqlite3")
            now = datetime(2026, 11, 11, tzinfo=timezone.utc)
            runtime = PaperRuntime(path, starting_cash="1000")
            runtime.enable(operator_approved=True)
            runtime.execute(symbol="BTC", side="BUY", quantity="1",
                            reference_mid="100", executed_price="100", fee="0",
                            quote_timestamp=now, now=now, marks={},
                            proposed_loss="1", aggregate_open_risk="0",
                            gross_notional="0", peak_nav="1000",
                            day_start_nav="1000", operator_approved=True,
                            order_id="recovery-001")
            runtime.close()
            recovered = PaperRuntime(path, starting_cash="1000")
            try:
                self.assertTrue(recovered.ledger.halted)
                self.assertEqual(recovered.ledger.cash, Decimal("900"))
                self.assertEqual(recovered.ledger.positions["BTC"], Decimal("1"))
                self.assertEqual(recovered.ledger.sequence, 1)
            finally:
                recovered.close()


if __name__ == "__main__":
    unittest.main()
