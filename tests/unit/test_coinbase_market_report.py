"""Offline contract tests for the read-only Coinbase report."""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from alpha_lab.research.live_paper_quotes import PaperQuote
from alpha_lab.research.coinbase_market_report import market_report

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def quote(symbol, age=1):
    event = NOW - timedelta(seconds=age)
    return PaperQuote(symbol, Decimal("100"), Decimal("100.1"), NOW,
                      "Coinbase Exchange level 1", exchange_at=event,
                      source_timestamp=event.isoformat(), source_sequence=12,
                      bid_size=Decimal("2"), ask_size=Decimal("3"))


class MarketReportTests(unittest.TestCase):
    def test_verified_three_products_no_execution(self):
        result = market_report(fetch=lambda symbol: quote(symbol), clock=lambda: NOW)
        self.assertEqual([r["status"] for r in result["markets"]], ["VERIFIED"] * 3)
        self.assertFalse(result["live_execution_authorised"])
        self.assertEqual(result["markets"][0]["spread_bps"], str(Decimal("0.1") / Decimal("100.05") * 10000))

    def test_stale_quote_fails_closed(self):
        result = market_report(fetch=lambda symbol: quote(symbol, age=20), clock=lambda: NOW)
        self.assertTrue(all(r["status"] == "UNVERIFIED" and r["mid_usd"] is None for r in result["markets"]))

    def test_provider_outage_is_unverified(self):
        def fail(_symbol):
            raise TimeoutError("offline")
        result = market_report(fetch=fail, clock=lambda: NOW)
        self.assertTrue(all(r["reason"] == "TimeoutError" for r in result["markets"]))

    def test_one_bad_symbol_does_not_hide_good_symbols(self):
        def fetch(symbol):
            if symbol == "ETH-USD":
                raise ValueError("invalid depth")
            return quote(symbol)
        result = market_report(fetch=fetch, clock=lambda: NOW)
        self.assertEqual([r["status"] for r in result["markets"]], ["VERIFIED", "UNVERIFIED", "VERIFIED"])


if __name__ == "__main__":
    unittest.main()
