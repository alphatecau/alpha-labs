"""Isolated simulated-fill -> SQLite backup -> recovery acceptance.

Uses no exchange network, Coinbase credentials, real orders or persistent journals.
"""
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from alpha_lab.research.paper_runtime import PaperRuntime


class PaperFillBackupRecoveryAcceptance(unittest.TestCase):
    def test_one_fill_backup_and_recovery_halts(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory(prefix="alpha-stage8-") as directory:
            original = Path(directory) / "paper.sqlite3"
            backup = Path(directory) / "paper-backup.sqlite3"
            runtime = PaperRuntime(str(original))
            order = dict(
                symbol="BTC-USD",
                side="BUY",
                quantity="0.001",
                reference_mid="70000",
                executed_price="70010",
                fee="0.07001",
                quote_timestamp=now,
                now=now,
                marks={},
                proposed_loss="2",
                aggregate_open_risk="0",
                gross_notional="0",
                peak_nav="10000",
                day_start_nav="10000",
                operator_approved=True,
                order_id="stage8-simulated-only-0001",
            )
            try:
                self.assertTrue(runtime.recovery_verified)
                self.assertTrue(runtime.ledger.halted)
                with self.assertRaises(PermissionError):
                    runtime.execute(**order)
                self.assertEqual(len(runtime.events), 0)
                runtime.enable(operator_approved=True)
                fill = runtime.execute(**order)
                self.assertTrue(fill["simulated"])
                self.assertEqual(len(runtime.events), 1)
                expected_head = runtime.journal_head
                with sqlite3.connect(str(backup)) as destination:
                    runtime.journal.connection.backup(destination)
                    self.assertEqual(destination.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                runtime.close()

            for path in (original, backup):
                recovered = PaperRuntime(str(path))
                try:
                    self.assertTrue(recovered.recovery_verified)
                    self.assertTrue(recovered.ledger.halted)
                    self.assertEqual(len(recovered.events), 1)
                    self.assertEqual(recovered.journal_head, expected_head)
                    self.assertEqual(recovered.events[0]["order_id"], order["order_id"])
                    with self.assertRaises(PermissionError):
                        recovered.execute(**order)
                    self.assertEqual(len(recovered.events), 1)
                finally:
                    recovered.close()


if __name__ == "__main__":
    unittest.main()
