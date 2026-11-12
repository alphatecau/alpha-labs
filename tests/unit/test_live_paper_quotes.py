"""Offline unit tests: no network and no broker credentials."""
import unittest
from datetime import datetime, timedelta, timezone

from alpha_lab.research.live_paper_quotes import (
    fetch_public_quote,
    parse_book_ticker,
    quote_is_fresh,
    simulated_fill_estimate,
)

NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)
PAYLOAD = {"symbol": "BTCUSDT", "bidPrice": "100", "askPrice": "101"}


class LivePaperQuotesTests(unittest.TestCase):
    def test_valid_quote_and_costs(self):
        q = parse_book_ticker(PAYLOAD, symbol="BTCUSDT", observed_at=NOW)
        self.assertEqual(str(q.mid), "100.5")
        self.assertTrue(quote_is_fresh(q, now=NOW + timedelta(seconds=5)))
        self.assertFalse(quote_is_fresh(q, now=NOW + timedelta(seconds=11)))
        buy = simulated_fill_estimate(q, side="BUY", quantity="1")
        sell = simulated_fill_estimate(q, side="SELL", quantity="1")
        self.assertIs(buy["live_execution_authorised"], False)
        self.assertGreater(float(buy["executed_price"]), 101)
        self.assertLess(float(sell["executed_price"]), 100)

    def test_reject_invalid_quotes(self):
        payloads = [
            {"symbol": "ETHUSDT", "bidPrice": "100", "askPrice": "101"},
            {"symbol": "BTCUSDT", "bidPrice": "102", "askPrice": "101"},
            {"symbol": "BTCUSDT", "bidPrice": "NaN", "askPrice": "101"},
            {"symbol": "BTCUSDT", "bidPrice": "0", "askPrice": "101"},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    parse_book_ticker(payload, symbol="BTCUSDT", observed_at=NOW)

    def test_no_unapproved_symbols_or_naive_timestamps(self):
        with self.assertRaises(ValueError):
            fetch_public_quote("DOGEUSDT")
        with self.assertRaises(ValueError):
            parse_book_ticker(PAYLOAD, symbol="BTCUSDT", observed_at=NOW.replace(tzinfo=None))

    def test_no_live_execution_side_effect(self):
        q = parse_book_ticker(PAYLOAD, symbol="BTCUSDT", observed_at=NOW)
        with self.assertRaises(ValueError):
            simulated_fill_estimate(q, side="SHORT", quantity="1")
        with self.assertRaises(ValueError):
            simulated_fill_estimate(q, side="BUY", quantity="-1")


if __name__ == "__main__":
    unittest.main()
