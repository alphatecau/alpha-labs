"""Regression for observed Android/Coinbase subsecond future exchange timestamps."""
import unittest
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory

from alpha_lab.research.coinbase_paper_book import (
    MAX_AGE, MAX_FUTURE_SKEW, PRODUCTS, executable, parse_book,
)
from alpha_lab.research.live_paper_session import LivePaperSession, PaperRejection


class TestCoinbaseFutureClockTolerance(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 12, 14, 30, tzinfo=timezone.utc)

    def book(self, offset_ms):
        exchange_time = self.now + timedelta(milliseconds=offset_ms)
        return {
            "auction_mode": False, "sequence": 123,
            "time": exchange_time.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "bids": [["100.00", "2.0", 1]],
            "asks": [["100.01", "2.0", 1]],
        }

    def test_bounded_future_clock_lead_is_accepted_by_the_adapter(self):
        for offset in (0, 136, 220, 500):
            with self.subTest(offset=offset):
                quote = parse_book("BTC-USD", self.book(offset), self.now)
                self.assertTrue(executable(quote, self.now))

    def test_larger_future_lead_is_rejected(self):
        for offset in (501, 1000, 10000):
            with self.subTest(offset=offset):
                with self.assertRaisesRegex(ValueError, "stale or future"):
                    parse_book("BTC-USD", self.book(offset), self.now)

    def test_stale_book_still_rejected(self):
        for age_ms in (10001, 11000, 30000):
            with self.subTest(age_ms=age_ms):
                with self.assertRaisesRegex(ValueError, "stale or future"):
                    parse_book("BTC-USD", self.book(-age_ms), self.now)

    def test_accepted_quote_becomes_stale_and_halts(self):
        quote = parse_book("BTC-USD", self.book(220), self.now)
        self.assertFalse(executable(quote, self.now + MAX_AGE + timedelta(milliseconds=221)))

    def test_invalid_quote_sequence_still_rejected(self):
        body = self.book(220)
        body["sequence"] = -1
        with self.assertRaisesRegex(ValueError, "sequence"):
            parse_book("BTC-USD", body, self.now)

    def test_limits_are_exact(self):
        self.assertEqual(MAX_FUTURE_SKEW, timedelta(milliseconds=500))
        self.assertEqual(MAX_AGE, timedelta(seconds=10))

    def test_clock_lead_halts_an_armed_session_until_explicit_rearm(self):
        books = {symbol: parse_book(symbol, self.book(0), self.now) for symbol in PRODUCTS}
        now = self.now

        class Feed:
            def snapshot(self, stamp):
                return books, {symbol: executable(quote, stamp) for symbol, quote in books.items()}, {}

        with TemporaryDirectory() as path:
            paper = LivePaperSession(path, "clock_skew_test_account", Feed(), clock=lambda: now)
            try:
                order = {"order_id": "clock_skew_book_order_01", "symbol": "SOL-USD",
                         "side": "BUY", "quantity": "1", "stop_price": "90"}
                paper.control("arm", expected_revision=paper.state()["risk"]["revision"])
                books["SOL-USD"] = parse_book("SOL-USD", self.book(220), self.now)
                state = paper.state()
                self.assertFalse(state["risk"]["data_healthy"])
                self.assertFalse(state["risk"]["armed"])
                self.assertEqual(state["risk"]["reason"], "MARKET_DATA_HALT")
                with self.assertRaisesRegex(PaperRejection, "Fresh books"):
                    paper.control("arm", expected_revision=state["risk"]["revision"])
                now += timedelta(milliseconds=220)
                paper.on_market_update()
                with self.assertRaisesRegex(PaperRejection, "execution is halted"):
                    paper.order(order)
                self.assertEqual(paper.runtime.ledger.sequence, 0)
                paper.control("arm", expected_revision=paper.state()["risk"]["revision"])
                self.assertEqual(paper.order(order)["status"], "SIMULATED_FILL")
            finally:
                paper.close()


if __name__ == "__main__":
    unittest.main()
