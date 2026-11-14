"""Offline safety acceptance: temporary journals only, no network or broker."""
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

from alpha_lab.research.local_paper_terminal import command
from alpha_lab.research.paper_market import COINBASE_MARKET
from alpha_lab.research.paper_risk import PaperRiskLimits, authorise_simulated_order
from alpha_lab.research.paper_runtime import PaperRuntime


class LocalPaperAcceptance(unittest.TestCase):
    def test_policy_thresholds_and_fail_closed_inputs(self):
        limits = PaperRiskLimits()
        self.assertEqual(limits.max_position_risk_pct, Decimal("0.0025"))
        self.assertEqual(limits.max_aggregate_risk_pct, Decimal("0.01"))
        self.assertEqual(limits.daily_loss_halt_pct, Decimal("0.02"))
        self.assertEqual(limits.drawdown_halt_pct, Decimal("0.05"))
        self.assertEqual(limits.max_notional_multiple, Decimal("1"))
        baseline = dict(nav="10000", initial_nav="10000", peak_nav="10000",
                        day_start_nav="10000", proposed_loss="1",
                        aggregate_open_risk="0", gross_notional="0",
                        proposed_notional="100", data_fresh=True,
                        ledger_reconciled=True, operator_enabled=True)
        self.assertTrue(authorise_simulated_order(**baseline)["approved"])
        cases = (
            (dict(proposed_loss="25.01"), "position risk exceeded"),
            (dict(aggregate_open_risk="100"), "aggregate risk exceeded"),
            (dict(nav="9800"), "daily loss HALT"),
            (dict(nav="9500", day_start_nav="9500"), "drawdown HALT"),
            (dict(gross_notional="9950"), "gross notional exceeded"),
            (dict(data_fresh=False), "stale or unverified market data"),
            (dict(ledger_reconciled=False), "unreconciled ledger"),
            (dict(operator_enabled=False), "operator HALT"),
        )
        for changes, reason in cases:
            with self.subTest(reason=reason):
                result = authorise_simulated_order(**(baseline | changes))
                self.assertFalse(result["approved"])
                self.assertIn(reason, result["reasons"])
                self.assertFalse(result["live_execution_authorised"])

    def test_recovery_requires_manual_rearm_and_preserves_fills(self):
        with tempfile.TemporaryDirectory(prefix="alpha-paper-accept-") as tmp:
            path = Path(tmp) / "isolated.sqlite3"
            now = datetime(2026, 11, 12, tzinfo=timezone.utc)
            runtime = PaperRuntime(str(path))
            self.assertTrue(runtime.recovery_verified)
            self.assertTrue(runtime.ledger.halted)
            runtime.enable(operator_approved=True)
            args = dict(symbol="BTC-USD", side="BUY", quantity="0.001",
                        reference_mid="70000", executed_price="70010",
                        fee="0.07001", quote_timestamp=now, now=now,
                        marks={}, proposed_loss="2", aggregate_open_risk="0",
                        gross_notional="0", peak_nav="10000",
                        day_start_nav="10000", operator_approved=True,
                        order_id="acceptance-order-0001")
            runtime.execute(**args)
            cash = runtime.ledger.cash
            runtime.close()
            restored = PaperRuntime(str(path))
            try:
                self.assertTrue(restored.recovery_verified)
                self.assertTrue(restored.ledger.halted)
                self.assertEqual(restored.ledger.cash, cash)
                self.assertEqual(restored.ledger.positions["BTC-USD"], Decimal("0.001"))
                self.assertEqual(len(restored.events), 1)
                with self.assertRaises(PermissionError):
                    restored.execute(**args)
            finally:
                restored.close()

    def test_tampered_event_rejected_without_touching_original(self):
        with tempfile.TemporaryDirectory(prefix="alpha-paper-tamper-") as tmp:
            path = Path(tmp) / "tampered.sqlite3"
            runtime = PaperRuntime(str(path))
            runtime.close()
            with sqlite3.connect(path) as db:
                db.execute("INSERT INTO events(seq,previous_hash,payload,digest) VALUES (1,?,?,?)",
                           ("0" * 64, '{"type":"FILL","simulated":true}', "0" * 64))
            with self.assertRaises((ValueError, sqlite3.Error)):
                PaperRuntime(str(path))

    def test_terminal_rejects_unverified_markets_and_shell(self):
        session = Mock()
        session.market = COINBASE_MARKET
        for line in ("buy SPY 1 400", "buy AAPL 1 100",
                     "buy BTC-USD 0.001", "shell whoami",
                     "sell SOL-USD 0.1 extra"):
            with self.subTest(line=line):
                with self.assertRaises(ValueError):
                    command(session, line)
        session.order.assert_not_called()


if __name__ == "__main__":
    unittest.main()
