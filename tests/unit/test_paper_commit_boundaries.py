"""Real SQLite/process boundaries, synthetic prices only; never broker execution."""
import http.client
import json
import multiprocessing
import os
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

from alpha_lab.research.coinbase_paper_book import PRODUCTS, parse_book
from alpha_lab.research.live_paper_session import LivePaperSession, PaperRejection
from alpha_lab.research.paper_journal import PaperJournal
from alpha_lab.research.paper_market_feed import PaperMarketFeed

NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)
ACCOUNT = "synthetic_paper_account"
ORDER = {"order_id": "commit_boundary_order_0001", "symbol": "SOL-USD", "side": "BUY",
         "quantity": "1", "stop_price": "90"}


def fixed_quote(symbol):
    return parse_book(symbol, {"auction_mode": False, "sequence": 100,
        "time": NOW.isoformat().replace("+00:00", "Z"), "bids": [["100", "100", 1]], "asks": [["100.02", "100", 1]]}, NOW)


class FixedFeed:
    def snapshot(self, now):
        return ({s: fixed_quote(s) for s in PRODUCTS}, dict.fromkeys(PRODUCTS, True), {})


def interrupted_fill(directory, committed):
    paper = LivePaperSession(directory, ACCOUNT, FixedFeed(), clock=lambda: NOW)
    paper.control("arm", expected_revision=paper.state()["risk"]["revision"])
    connection = paper.runtime.journal.connection

    class CommitBoundary:
        def __getattr__(self, name):
            return getattr(connection, name)

        def commit(self):
            if committed:
                connection.commit()
            os._exit(74 if committed else 73)

    paper.runtime.journal.connection = CommitBoundary()
    paper.order(ORDER)
    os._exit(75)


class PaperCommitBoundaryTests(unittest.TestCase):
    def test_tampered_identity_schema_is_rejected_and_writer_lock_released(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "forged.sqlite3"
            with sqlite3.connect(path) as connection:
                connection.execute("CREATE TABLE events(seq INTEGER PRIMARY KEY, previous_hash TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL, order_id TEXT GENERATED ALWAYS AS (NULL) VIRTUAL)")
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, "generated order identity"):
                    PaperJournal(path)

    def test_duplicate_json_order_members_cannot_disagree_with_database_index(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicates.sqlite3"
            journal = PaperJournal(path)
            payload = '{"type":"TEST","order_id":"first_order_0001","order_id":"other_order_0001"}'
            digest = sha256(("0" * 64 + payload).encode()).hexdigest()
            journal.connection.execute("INSERT INTO events(previous_hash,payload,digest) VALUES(?,?,?)", ("0" * 64, payload, digest))
            journal.connection.commit()
            journal.close()
            with self.assertRaisesRegex(ValueError, "duplicate journal JSON"):
                PaperJournal(path)

    def test_process_exit_before_and_after_commit_replays_exactly_once(self):
        ctx = multiprocessing.get_context("spawn")
        for committed in (False, True):
            with self.subTest(committed=committed), tempfile.TemporaryDirectory() as directory:
                initial = LivePaperSession(directory, ACCOUNT, FixedFeed(), clock=lambda: NOW)
                initial.close()
                process = ctx.Process(target=interrupted_fill, args=(directory, committed))
                process.start()
                process.join(timeout=10)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
                    self.fail("disposable crash worker did not finish")
                self.assertEqual(process.exitcode, 74 if committed else 73)
                recovered = LivePaperSession(directory, ACCOUNT, FixedFeed(), clock=lambda: NOW)
                try:
                    self.assertTrue(recovered.runtime.ledger.halted)
                    self.assertEqual(recovered.runtime.ledger.sequence, int(committed))
                    if committed:
                        cash = recovered.runtime.ledger.cash
                        self.assertEqual(recovered.order(ORDER)["status"], "ALREADY_COMMITTED")
                        self.assertEqual(recovered.runtime.ledger.cash, cash)
                    else:
                        self.assertEqual(str(recovered.runtime.ledger.cash), "10000")
                        with self.assertRaises(PaperRejection):
                            recovered.order(ORDER)
                finally:
                    recovered.close()

    def test_database_unique_constraint_survives_concurrent_raw_connections(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.sqlite3"
            PaperJournal(path).close()
            barrier = threading.Barrier(2)
            payload = json.dumps({"type": "TEST", "order_id": "db_unique_order_0001"}, sort_keys=True)
            digest = sha256(("0" * 64 + payload).encode()).hexdigest()

            def insert():
                connection = sqlite3.connect(path, timeout=3)
                try:
                    barrier.wait(timeout=5)
                    with connection:
                        connection.execute("INSERT INTO events(previous_hash,payload,digest) VALUES(?,?,?)",
                                           ("0" * 64, payload, digest))
                    return "committed"
                except sqlite3.IntegrityError:
                    return "duplicate"
                finally:
                    connection.close()

            with ThreadPoolExecutor(2) as pool:
                results = list(pool.map(lambda _: insert(), range(2)))
            self.assertCountEqual(results, ["committed", "duplicate"])
            journal = PaperJournal(path)
            try:
                self.assertEqual(journal.verify(), digest)
                with self.assertRaises(sqlite3.OperationalError):
                    journal.connection.execute("UPDATE events SET order_id='different_id'")
                journal.connection.rollback()
            finally:
                journal.close()

    def test_old_schema_migrates_without_changing_payload_or_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.sqlite3"
            payload = '{"type":"TEST","order_id":"legacy_unique_order_0001"}'
            digest = sha256(("0" * 64 + payload).encode()).hexdigest()
            with sqlite3.connect(path) as connection:
                connection.execute("CREATE TABLE events(seq INTEGER PRIMARY KEY, previous_hash TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL)")
                connection.execute("INSERT INTO events VALUES(1,?,?,?)", ("0" * 64, payload, digest))
            journal = PaperJournal(path)
            try:
                self.assertEqual(journal.verify(), digest)
                self.assertEqual(journal.connection.execute("SELECT payload FROM events").fetchone()[0], payload)
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    journal.append(json.loads(payload))
            finally:
                journal.close()

    def test_http_protocol_failure_invalidates_previous_quotes(self):
        feed = PaperMarketFeed(fetch=fixed_quote, clock=lambda: NOW)
        with ThreadPoolExecutor(3) as pool:
            feed.poll(pool)
            self.assertTrue(all(feed.snapshot(NOW)[1].values()))

            def broken(_):
                raise http.client.IncompleteRead(b"partial", 100)

            feed.fetch = broken
            feed.poll(pool)
        self.assertFalse(any(feed.snapshot(NOW)[1].values()))

    def test_watchdog_halts_stale_data_while_network_poll_is_blocked(self):
        now = [NOW]
        feed = PaperMarketFeed(fetch=fixed_quote, clock=lambda: now[0])
        with ThreadPoolExecutor(3) as pool:
            feed.poll(pool)
        blocked, release, halted = threading.Event(), threading.Event(), threading.Event()
        with tempfile.TemporaryDirectory() as directory:
            paper = LivePaperSession(directory, ACCOUNT, feed, clock=lambda: now[0])
            try:
                paper.control("arm", expected_revision=paper.state()["risk"]["revision"])

                def block(symbol):
                    blocked.set()
                    release.wait(timeout=3)
                    return fixed_quote(symbol)

                def watch():
                    paper.on_market_update()
                    if paper.runtime.ledger.halted:
                        halted.set()

                feed.fetch = block
                feed.start(watch, watchdog_interval=0.02)
                self.assertTrue(blocked.wait(timeout=2))
                now[0] += timedelta(seconds=11)
                self.assertTrue(halted.wait(timeout=2))
                self.assertFalse(release.is_set())
                self.assertEqual(paper._guard()["reason"], "MARKET_DATA_HALT")
            finally:
                release.set()
                feed.close()
                paper.close()
