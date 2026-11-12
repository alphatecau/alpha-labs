"""Offline-only Personal Edition order-id and durable append acceptance tests."""
import tempfile
import threading
import multiprocessing
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from alpha_lab.research.paper_runtime import PaperRuntime
from alpha_lab.research.paper_journal import PaperJournal


def _process_journal_append(path, barrier, outcomes, order_id):
    journal = None
    barrier.wait(timeout=10)
    try:
        try:
            journal = PaperJournal(path)
            journal.append({"type": "FILL", "simulated": True, "order_id": order_id},
                           expected_seq=0, expected_head="0" * 64)
            outcomes.put("committed")
        except PermissionError as exc:
            outcomes.put(str(exc))
        # Keep ownership until both contenders have attempted acquisition.
        barrier.wait(timeout=10)
    finally:
        if journal is not None:
            journal.close()


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
        try:
            with self.assertRaisesRegex(PermissionError, "already has a writer"):
                PaperRuntime(self.path, starting_cash="1000")
            first.enable(operator_approved=True)
            first.execute(**self.kw)
            self.assertEqual(first.ledger.sequence, 1)
        finally:
            first.close()
        recovered = PaperRuntime(self.path, starting_cash="1000")
        try:
            self.assertEqual(recovered.ledger.sequence, 1)
            self.assertEqual(recovered.ledger.cash, Decimal("900"))
        finally:
            recovered.close()

    def test_two_processes_only_one_stale_snapshot_commits(self):
        ctx = multiprocessing.get_context("spawn")
        barrier = ctx.Barrier(2)
        outcomes = ctx.Queue()
        processes = [
            ctx.Process(target=_process_journal_append,
                        args=(self.path, barrier, outcomes, "process-order-" + str(i)))
            for i in range(2)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=20)
        try:
            self.assertTrue(all(not p.is_alive() for p in processes))
            self.assertTrue(all(p.exitcode == 0 for p in processes))
            results = [outcomes.get(timeout=5) for _ in processes]
            self.assertEqual(results.count("committed"), 1)
            self.assertTrue(any("already has a writer" in x for x in results))
            verifier = PaperJournal(self.path)
            try:
                self.assertEqual(verifier.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)
                verifier.verify()
            finally:
                verifier.close()
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
            outcomes.close()

    def test_simultaneous_journal_writers_only_one_commits(self):
        barrier = threading.Barrier(2)
        outcomes = []
        lock = threading.Lock()
        def attempt(order_id):
            journal = None
            barrier.wait(timeout=10)
            try:
                try:
                    journal = PaperJournal(self.path)
                    journal.append({"type": "FILL", "simulated": True, "order_id": order_id},
                                   expected_seq=0, expected_head="0" * 64)
                    outcome = "committed"
                except PermissionError as exc:
                    outcome = str(exc)
                with lock:
                    outcomes.append(outcome)
                barrier.wait(timeout=10)
            finally:
                if journal is not None:
                    journal.close()
        a = threading.Thread(target=attempt, args=("concurrent-a",))
        b = threading.Thread(target=attempt, args=("concurrent-b",))
        a.start()
        b.start()
        a.join(timeout=10)
        b.join(timeout=10)
        self.assertFalse(a.is_alive() or b.is_alive())
        self.assertEqual(outcomes.count("committed"), 1)
        self.assertEqual(len(outcomes), 2)
        self.assertTrue(any("already has a writer" in x for x in outcomes))
        verifier = PaperJournal(self.path)
        try:
            self.assertEqual(verifier.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)
            verifier.verify()
        finally:
            verifier.close()

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
