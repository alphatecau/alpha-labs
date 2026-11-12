"""Regression for observed Android/Coinbase subsecond future exchange timestamps."""
import unittest
from datetime import datetime, timedelta, timezone

from alpha_lab.research.coinbase_paper_book import (
    MAX_AGE, MAX_FUTURE_SKEW, executable, parse_book,
)


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

    def test_bounded_future_clock_lead_is_accepted_for_parse_and_execution(self):
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


if __name__ == "__main__":
    unittest.main()
