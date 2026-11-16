"""Offline end-to-end research/paper boundary rehearsal; no broker or network.

The research report is informational only. Simulated fills require separate,
explicit operator approval and risk authorisation in an isolated SQLite journal.
"""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alpha_lab.research.coinbase_signal_report import research_report
from alpha_lab.research.paper_runtime import PaperRuntime


NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


def research_fixture():
    return {
        "schema_version": 1,
        "provider": "AlphaLabs Coinbase read-only",
        "product_id": "BTC-USD",
        "product_type": "SPOT",
        "quote_currency": "USD",
        "granularity": "4h",
        "collected_at": NOW.isoformat().replace("+00:00", "Z"),
        "candles": [
            {
                "start": (NOW - timedelta(hours=4 * (60 - i))).isoformat().replace("+00:00", "Z"),
                "open": str(100 + i),
                "high": str(102 + i),
                "low": str(99 + i),
                "close": str(101 + i),
                "volume": "5",
                "complete": True,
            }
            for i in range(60)
        ],
    }


class CoinbaseResearchPaperIsolation(unittest.TestCase):
    def test_research_never_arms_paper_runtime_and_recovery_halts(self):
        report = research_report(research_fixture(), now=NOW)
        self.assertEqual(report["decision"], "FLAT")
        self.assertEqual(report["risk_override"], "HALT")
        self.assertFalse(report["paper_execution_authorised"])
        self.assertFalse(report["live_execution_authorised"])

        with tempfile.TemporaryDirectory(prefix="alpha-coinbase-isolation-") as folder:
            path = Path(folder) / "isolated.sqlite3"
            runtime = PaperRuntime(str(path))
            args = dict(
                symbol="BTC-USD", side="BUY", quantity="0.001",
                reference_mid="70000", executed_price="70010", fee="0.07001",
                quote_timestamp=NOW, now=NOW, marks={},
                proposed_loss="2", aggregate_open_risk="0",
                gross_notional="0", peak_nav="10000",
                day_start_nav="10000", operator_approved=True,
                order_id="coinbase-isolation-test-0001",
            )
            try:
                self.assertTrue(runtime.recovery_verified)
                self.assertTrue(runtime.ledger.halted)
                with self.assertRaises(PermissionError):
                    runtime.execute(**args)
                self.assertEqual(len(runtime.events), 0)

                # Explicit paper-only operator action, independent of the research report.
                runtime.enable(operator_approved=True)
                runtime.execute(**args)
                self.assertEqual(len(runtime.events), 1)
            finally:
                runtime.close()

            restored = PaperRuntime(str(path))
            try:
                self.assertTrue(restored.recovery_verified)
                self.assertTrue(restored.ledger.halted)
                self.assertEqual(len(restored.events), 1)
                with self.assertRaises(PermissionError):
                    restored.execute(**args)
                self.assertEqual(len(restored.events), 1)
            finally:
                restored.close()

    def test_rejected_snapshot_does_not_create_a_journal(self):
        data = research_fixture()
        data["candles"][-1]["complete"] = False
        with tempfile.TemporaryDirectory(prefix="alpha-coinbase-reject-") as folder:
            path = Path(folder) / "no-journal.sqlite3"
            with self.assertRaises(ValueError):
                research_report(data, now=NOW)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
