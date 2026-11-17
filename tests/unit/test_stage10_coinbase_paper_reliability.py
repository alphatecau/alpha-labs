"""Stage 10 deterministic offline reliability and fail-closed acceptance.

No network, credentials, live orders, or persistent working journals.
"""
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from alpha_lab.research.coinbase_paper_book import PRODUCTS, parse_book
from alpha_lab.research.paper_market_feed import PaperMarketFeed
from alpha_lab.research.stage9_coinbase_paper_rehearsal import rehearse

NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


def make_book(at=NOW, sequence=1):
    return {"auction_mode": False, "time": at.isoformat().replace("+00:00", "Z"),
            "sequence": sequence, "bids": [["70000", "2", 1]],
            "asks": [["70001", "2", 1]]}


def quote(product="BTC-USD", at=NOW, sequence=1):
    return parse_book(product, make_book(at, sequence), at)


class Stage10Reliability(unittest.TestCase):
    def test_repeated_polling_all_products_and_expiry(self):
        sequence = [0]

        def fetch(product):
            return quote(product, NOW, sequence[0])

        feed = PaperMarketFeed(fetch=fetch, clock=lambda: NOW, retry_clock=lambda: 0)
        with ThreadPoolExecutor(max_workers=3) as pool:
            for i in range(1, 31):
                sequence[0] = i
                feed.poll(pool)
                quotes, healthy, _ = feed.snapshot(NOW)
                self.assertEqual(set(quotes), set(PRODUCTS))
                self.assertTrue(all(healthy.values()))
        self.assertFalse(any(feed.snapshot(NOW + timedelta(seconds=11))[1].values()))

    def test_sequence_regression_fails_closed(self):
        sequence = [2]
        feed = PaperMarketFeed(
            fetch=lambda product: quote(product, NOW, sequence[0]),
            clock=lambda: NOW, retry_clock=lambda: 0,
        )
        with ThreadPoolExecutor(max_workers=3) as pool:
            feed.poll(pool)
            self.assertTrue(all(feed.snapshot(NOW)[1].values()))
            sequence[0] = 1
            feed.poll(pool)
            self.assertFalse(any(feed.snapshot(NOW)[1].values()))

    def test_provider_outage_after_success_fails_closed(self):
        outage = [False]

        def fetch(product):
            if outage[0]:
                raise OSError("simulated Coinbase outage")
            return quote(product, NOW)

        feed = PaperMarketFeed(fetch=fetch, clock=lambda: NOW, retry_clock=lambda: 0)
        with ThreadPoolExecutor(max_workers=3) as pool:
            feed.poll(pool)
            self.assertTrue(all(feed.snapshot(NOW)[1].values()))
            outage[0] = True
            feed.poll(pool)
            self.assertFalse(any(feed.snapshot(NOW)[1].values()))

    def test_stage9_rehearsal_replays_original_and_backup(self):
        result = rehearse(fetch=lambda product: quote(product, NOW),
                          clock=lambda: NOW)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["fills"], 1)
        self.assertEqual(result["backup"], "VERIFIED")
        self.assertEqual(result["restart"], "HALT")
        self.assertIs(result["live_execution_authorised"], False)

    def test_stage9_rejects_expired_quote_without_paper_execution(self):
        old = NOW - timedelta(seconds=11)
        with patch("alpha_lab.research.stage9_coinbase_paper_rehearsal.PaperRuntime.execute",
                   side_effect=AssertionError("unsafe execution invoked")) as execute:
            with self.assertRaisesRegex(ValueError, "HALT"):
                rehearse(fetch=lambda product: quote(product, old),
                         clock=lambda: NOW)
            execute.assert_not_called()

    def test_stage9_provider_outage_never_executes(self):
        def unavailable(_product):
            raise OSError("simulated public provider outage")

        with patch("alpha_lab.research.stage9_coinbase_paper_rehearsal.PaperRuntime.execute",
                   side_effect=AssertionError("unsafe execution invoked")) as execute:
            with self.assertRaises(OSError):
                rehearse(fetch=unavailable, clock=lambda: NOW)
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
