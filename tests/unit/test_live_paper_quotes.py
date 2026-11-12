"""Offline adversarial checks compatible with unittest discovery."""
import unittest
from datetime import datetime, timezone, timedelta
from alpha_lab.research.live_paper_quotes import (
    parse_book_ticker, quote_is_fresh, simulated_fill_estimate, fetch_public_quote
)
NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)
PAYLOAD = {"symbol":"BTCUSDT","bidPrice":"100","askPrice":"101"}

class LivePaperQuoteTests(unittest.TestCase):
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
        for payload in (
            {"symbol":"ETHUSDT","bidPrice":"100","askPrice":"101"},
            {"symbol":"BTCUSDT","bidPrice":"102","askPrice":"101"},
            {"symbol":"BTCUSDT","bidPrice":"NaN","askPrice":"101"},
            {"symbol":"BTCUSDT","bidPrice":"0","askPrice":"101"},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_book_ticker(payload, symbol="BTCUSDT", observed_at=NOW)

    def test_reject_unsafe_inputs(self):
        with self.assertRaises(ValueError):
            fetch_public_quote("DOGEUSDT")
        with self.assertRaises(ValueError):
            parse_book_ticker(PAYLOAD, symbol="BTCUSDT", observed_at=NOW.replace(tzinfo=None))
        q = parse_book_ticker(PAYLOAD, symbol="BTCUSDT", observed_at=NOW)
        for side, quantity in (("SHORT","1"), ("BUY","-1")):
            with self.subTest(side=side, quantity=quantity), self.assertRaises(ValueError):
                simulated_fill_estimate(q, side=side, quantity=quantity)

if __name__ == "__main__":
    unittest.main()
