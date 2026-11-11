"""Offline-only Personal Edition order-id and durable append acceptance tests."""
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from alpha_lab.research.paper_runtime import PaperRuntime


class PersonalOrderIdTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "journal.sqlite3")
        self.now = datetime(2026, 11, 11, tzinfo=timezone.utc)
        self.kw = dict(symbol="BTC", side="BUY", quantity="1",
                       reference_mid="100", executed_price="100", fee="0",
                       quote_timestamp=self.now, now=self.now, marks={},
                       proposed_loss="1", aggregate_open_risk="0",
                       gross_notional="0", peak_nav="1000",
                       day_start_nav="1000", operator_approved=True,
                       order_id="research-order-001")

    def test_duplicate_rejected_in_process_and_after_restart(self):
        r = PaperRuntime(self.path, starting_cash="1000")
        r.enable(operator_approved=True)
        r.execute(**self.kw)
        with self.assertRaisesRegex(PermissionError, "duplicate simulated order"):
            r.execute(**self.kw)
        self.assertEqual(r.ledger.sequence, 1)
        self.assertEqual(r.ledger.cash, Decimal("900"))
        r.close()
        recovered = PaperRuntime(self.path, starting_cash="1000")
        try:
            recovered.enable(operator_approved=True)
            with self.assertRaisesRegex(PermissionError, "duplicate simulated order"):
                recovered.execute(**self.kw)
            self.assertEqual(recovered.ledger.sequence, 1)
            self.assertEqual(recovered.ledger.cash, Decimal("900"))
        finally:
            recovered.close()

    def test_two_runtime_instances_cannot_commit_stale_or_duplicate_orders(self):
        first = PaperRuntime(self.path, starting_cash="1000")
        second = PaperRuntime(self.path, starting_cash="1000")
        try:
            first.enable(operator_approved=True)
            second.enable(operator_approved=True)
            first.execute(**self.kw)
            with self.assertRaisesRegex(ValueError, "stale journal state"):
                second.execute(**self.kw)
            self.assertTrue(second.ledger.halted)
            self.assertEqual(second.ledger.sequence, 0)
            self.assertEqual(second.ledger.cash, Decimal("1000"))
            second.enable(operator_approved=True)
            with self.assertRaisesRegex(ValueError, "stale journal state"):
                second.execute(**(self.kw | {"order_id": "research-order-002"}))
            self.assertTrue(second.ledger.halted)
            self.assertEqual(second.ledger.sequence, 0)
            self.assertEqual(first.ledger.sequence, 1)
        finally:
            first.close()
            second.close()
        recovered = PaperRuntime(self.path, starting_cash="1000")
        try:
            self.assertEqual(recovered.ledger.sequence, 1)
            self.assertEqual(recovered.ledger.cash, Decimal("900"))
        finally:
            recovered.close()

    def test_append_failure_cannot_change_authoritative_ledger(self):
        r = PaperRuntime(self.path, starting_cash="1000")
        try:
            r.enable(operator_approved=True)
            with patch.object(r.journal, "append", side_effect=OSError("disk failure")):
                with self.assertRaisesRegex(OSError, "disk failure"):
                    r.execute(**self.kw)
            self.assertEqual(r.ledger.sequence, 0)
            self.assertEqual(r.ledger.cash, Decimal("1000"))
            self.assertEqual(r.order_ids, set())
            self.assertTrue(r.ledger.halted)
        finally:
            r.close()

    def test_missing_order_id_halts_without_fill(self):
        r = PaperRuntime(self.path, starting_cash="1000")
        try:
            r.enable(operator_approved=True)
            with self.assertRaisesRegex(ValueError, "mandatory order ID"):
                r.execute(**(self.kw | {"order_id": None}))
            self.assertTrue(r.ledger.halted)
            self.assertEqual(r.ledger.sequence, 0)
        finally:
            r.close()

    def test_invalid_order_id_halts(self):
        r = PaperRuntime(self.path, starting_cash="1000")
        try:
            r.enable(operator_approved=True)
            with self.assertRaisesRegex(ValueError, "mandatory order ID"):
                r.execute(**(self.kw | {"order_id": ""}))
            self.assertTrue(r.ledger.halted)
            self.assertEqual(r.ledger.sequence, 0)
        finally:
            r.close()


if __name__ == "__main__":
    unittest.main()
