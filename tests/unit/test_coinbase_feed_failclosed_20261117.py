"""Offline public Coinbase paper-feed fail-closed tests: no network or orders."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from alpha_lab.research.coinbase_paper_book import PRODUCTS, parse_book
from alpha_lab.research.paper_market_feed import PaperMarketFeed


NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


def book(*, at=NOW, sequence=10, bid="100", ask="101"):
    return {
        "auction_mode": False,
        "time": at.isoformat().replace("+00:00", "Z"),
        "sequence": sequence,
        "bids": [[bid, "5", 1]],
        "asks": [[ask, "5", 1]],
    }


class CoinbaseFeedFailClosed(unittest.TestCase):
    def test_valid_quote_expires_without_fresh_poll(self):
        def fetch(product):
            return parse_book(product, book(), NOW)

        feed = PaperMarketFeed(fetch=fetch, clock=lambda: NOW, retry_clock=lambda: 0)
        with ThreadPoolExecutor(max_workers=3) as pool:
            feed.poll(pool)
        _, healthy, _ = feed.snapshot(NOW)
        self.assertTrue(all(healthy[p] for p in PRODUCTS))
        _, expired, _ = feed.snapshot(NOW + timedelta(seconds=11))
        self.assertFalse(any(expired.values()))

    def test_bad_product_quote_cannot_hide_failure(self):
        def fetch(product):
            if product == "ETH-USD":
                return parse_book("BTC-USD", book(), NOW)
            return parse_book(product, book(), NOW)

        feed = PaperMarketFeed(fetch=fetch, clock=lambda: NOW, retry_clock=lambda: 0)
        with ThreadPoolExecutor(max_workers=3) as pool:
            feed.poll(pool)
        _, healthy, _ = feed.snapshot(NOW)
        self.assertFalse(healthy["ETH-USD"])
        self.assertTrue(healthy["BTC-USD"])
        self.assertTrue(healthy["SOL-USD"])

    def test_future_and_stale_exchange_timestamps_are_rejected(self):
        for offset in (timedelta(seconds=2), -timedelta(seconds=11)):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                parse_book("BTC-USD", book(at=NOW + offset), NOW)

    def test_crossed_book_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_book("BTC-USD", book(bid="102", ask="101"), NOW)

    def test_network_failure_leaves_all_products_unverified(self):
        def fetch(_product):
            raise OSError("offline test outage")

        feed = PaperMarketFeed(fetch=fetch, clock=lambda: NOW, retry_clock=lambda: 0)
        with ThreadPoolExecutor(max_workers=3) as pool:
            feed.poll(pool)
        _, healthy, _ = feed.snapshot(NOW)
        self.assertFalse(any(healthy.values()))


if __name__ == "__main__":
    unittest.main()
