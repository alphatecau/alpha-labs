"""Offline acceptance for bounded, read-only Stage 11 soak reporting."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from alpha_lab.research.coinbase_paper_book import PRODUCTS
from alpha_lab.research.stage11_coinbase_soak import observe

NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.seconds = 0.0

    def monotonic(self):
        return self.seconds

    def sleep(self, seconds):
        self.seconds += seconds


class FakeQuote:
    exchange_at = NOW - timedelta(seconds=2)


class FakeFeed:
    def __init__(self, degraded=None):
        self.polls = 0
        self.degraded = degraded or set()

    def poll(self, _pool):
        self.polls += 1

    def snapshot(self, _now):
        return ({p: FakeQuote() for p in PRODUCTS},
                {p: p not in self.degraded for p in PRODUCTS}, {})


class Stage11SoakMetrics(unittest.TestCase):
    def test_all_healthy_counts_and_zero_orders(self):
        clock, feed = Clock(), FakeFeed()
        result = observe(duration_seconds=30, interval_seconds=15, feed=feed,
                         clock=lambda: NOW, monotonic=clock.monotonic,
                         sleep=clock.sleep)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["samples"], 3)
        self.assertEqual(feed.polls, 3)
        self.assertEqual(result["paper_orders"], 0)
        self.assertEqual(result["live_orders"], 0)
        self.assertIs(result["live_execution_authorised"], False)
        for product in PRODUCTS:
            self.assertEqual(result["products"][product]["availability_pct"], 100)
            self.assertEqual(result["products"][product]["max_exchange_age_seconds"], 2)

    def test_unverified_quote_reports_degraded(self):
        clock, feed = Clock(), FakeFeed(degraded={"ETH-USD"})
        result = observe(duration_seconds=30, interval_seconds=15, feed=feed,
                         clock=lambda: NOW, monotonic=clock.monotonic,
                         sleep=clock.sleep)
        self.assertEqual(result["status"], "DEGRADED")
        self.assertEqual(result["products"]["ETH-USD"]["healthy"], 0)
        self.assertEqual(result["products"]["ETH-USD"]["unverified"], 3)
        self.assertEqual(result["products"]["ETH-USD"]["availability_pct"], 0)
        self.assertEqual(result["products"]["BTC-USD"]["availability_pct"], 100)

    def test_bounded_configuration_rejected_before_network(self):
        with patch("alpha_lab.research.stage11_coinbase_soak.PaperMarketFeed") as constructor:
            for duration, interval in ((29, 15), (7201, 15), (30, 1), (30, 121)):
                with self.subTest(duration=duration, interval=interval):
                    with self.assertRaises(ValueError):
                        observe(duration_seconds=duration, interval_seconds=interval)
            constructor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
