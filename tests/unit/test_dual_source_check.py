"""Deterministic offline tests: no network, keys or order placement."""
import json
import unittest
from decimal import Decimal
from unittest.mock import patch

from alpha_lab.data.dual_source_check import MarketDataHalt, crosscheck, _timestamp

NOW = 1_800_000_000


def fixture(url, headers=None):
    if "binance" in url:
        return [{"price": "100.0", "time": NOW * 1000}]
    return {"bitcoin": {"usd": 101.0, "last_updated_at": NOW}}


class DualSourceTests(unittest.TestCase):
    @patch("alpha_lab.data.dual_source_check._json_get", side_effect=fixture)
    def test_accepts_fresh_consistent_prices(self, mocked):
        result = crosscheck("BTC", now=NOW)
        self.assertEqual(result["status"], "VERIFIED_RESEARCH_DATA")
        self.assertEqual(result["binance_symbol"], "BTCUSDT")
        self.assertEqual(mocked.call_count, 2)

    @patch("alpha_lab.data.dual_source_check._json_get")
    def test_rejects_divergence(self, mocked):
        mocked.side_effect = [
            [{"price": "100", "time": NOW * 1000}],
            {"bitcoin": {"usd": 120, "last_updated_at": NOW}},
        ]
        with self.assertRaisesRegex(MarketDataHalt, "deviation"):
            crosscheck("BTC", now=NOW)

    @patch("alpha_lab.data.dual_source_check._json_get")
    def test_rejects_stale_trade(self, mocked):
        mocked.return_value = [{"price": "100", "time": (NOW - 301) * 1000}]
        with self.assertRaisesRegex(MarketDataHalt, "stale"):
            crosscheck("BTC", now=NOW)
        self.assertEqual(mocked.call_count, 1)

    @patch("alpha_lab.data.dual_source_check._json_get")
    def test_rejects_missing_coingecko_timestamp(self, mocked):
        mocked.side_effect = [
            [{"price": "100", "time": NOW * 1000}],
            {"bitcoin": {"usd": 100}},
        ]
        with self.assertRaisesRegex(MarketDataHalt, "timestamp"):
            crosscheck("BTC", now=NOW)

    @patch("alpha_lab.data.dual_source_check._json_get")
    def test_rejects_invalid_prices(self, mocked):
        mocked.return_value = [{"price": "NaN", "time": NOW * 1000}]
        with self.assertRaisesRegex(MarketDataHalt, "price"):
            crosscheck("BTC", now=NOW)

    @patch("alpha_lab.data.dual_source_check._json_get")
    def test_rejects_provider_failure(self, mocked):
        mocked.side_effect = MarketDataHalt("market data request failed")
        with self.assertRaises(MarketDataHalt):
            crosscheck("BTC", now=NOW)

    def test_rejects_unknown_asset(self):
        with self.assertRaisesRegex(MarketDataHalt, "unsupported"):
            crosscheck("DOGE", now=NOW)

    def test_rejects_future_timestamp(self):
        with self.assertRaisesRegex(MarketDataHalt, "future"):
            _timestamp(NOW + 31, NOW)

    def test_rejects_invalid_policy(self):
        with self.assertRaisesRegex(MarketDataHalt, "policy"):
            crosscheck("BTC", now=NOW, max_deviation=Decimal("0.9"))


if __name__ == "__main__":
    unittest.main()
