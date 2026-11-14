"""Offline acceptance for the live-paper contract and failure boundaries."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import io
from email.message import Message
from urllib.error import HTTPError
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

from alpha_lab.research.coinbase_paper_book import PRODUCTS, executable, fetch_book, parse_book
from alpha_lab.research.live_paper_session import LivePaperSession, PaperRejection
from alpha_lab.research.paper_market_feed import PaperMarketFeed

ACCOUNT = "paper_owner_test_account"


def book(now, bid="100.00", ask="100.02", sequence=100, size="100.0"):
    return {"auction_mode": False, "sequence": sequence,
            "time": now.isoformat().replace("+00:00", "Z"),
            "bids": [[bid, size, 2]], "asks": [[ask, size, 2]]}


class PaperMarketTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 12, 5, tzinfo=timezone.utc)

    def test_source_time_is_separate_from_receive_time(self):
        source = self.now - timedelta(seconds=2)
        body = book(source)
        body["time"] = "2026-11-12T04:59:58.000000123Z"
        quote = parse_book("BTC-USD", body, self.now)
        self.assertEqual(quote.source_timestamp, body["time"])
        self.assertEqual(quote.exchange_at, source)
        self.assertEqual(quote.observed_at, self.now)
        self.assertFalse(executable(quote, self.now + timedelta(seconds=9)))

    def test_rejects_auction_stale_future_crossed_zero_and_bad_sequence(self):
        for mutations in (
            {"auction_mode": True},
            {"time": book(self.now - timedelta(seconds=11))["time"]},
            {"time": book(self.now + timedelta(seconds=1))["time"]},
            {"bids": [["120", "2", 1]]},
            {"asks": [["100.02", "0", 1]]},
            {"bids": [["NaN", "3", 1]]},
            {"sequence": True},
            {"time": None},
        ):
            with self.subTest(mutations=mutations), self.assertRaises(ValueError):
                parse_book("SOL-USD", {**book(self.now), **mutations}, self.now)

    def test_fetch_is_public_bounded_and_rejects_changed_origin(self):
        class Response(io.BytesIO):
            status = 200

            def geturl(self):
                return self.url

        def opener(request, timeout):
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(timeout, 8)
            self.assertEqual(request.get_header("Cache-control"), "no-cache, no-store, max-age=0")
            self.assertIsNone(request.get_header("Authorization"))
            response = Response(json.dumps(book(self.now)).encode())
            response.url = request.full_url
            response.headers = Message()
            response.headers["Content-Type"] = "application/json"
            return response

        quote = fetch_book("BTC-USD", opener=opener, clock=lambda: self.now)
        self.assertEqual(quote.symbol, "BTC-USD")

        def foreign_origin(request, timeout):
            response = opener(request, timeout)
            response.url = "https://unexpected.example/book"
            return response

        with self.assertRaisesRegex(ValueError, "unexpected provider response"):
            fetch_book("BTC-USD", opener=foreign_origin, clock=lambda: self.now)

    def test_feed_invalidates_regressions_and_preserves_only_observed_history(self):
        payload = book(self.now)
        feed = PaperMarketFeed(fetch=lambda product: parse_book(product, payload, self.now),
                              clock=lambda: self.now)
        with ThreadPoolExecutor(3) as pool:
            feed.poll(pool)
            self.assertTrue(all(feed.snapshot(self.now)[1].values()))
            payload["sequence"] -= 1
            feed.poll(pool)
            quotes, healthy, history = feed.snapshot(self.now)
        self.assertFalse(any(healthy.values()))
        self.assertEqual(quotes["SOL-USD"].source_sequence, 100)
        self.assertEqual(len(history["SOL-USD"]), 1)

    def test_provider_429_immediately_invalidates_all_books_and_backs_off(self):
        now = 100
        throttle = False
        calls = []

        def fetch(product):
            calls.append(product)
            if throttle and product == "SOL-USD":
                headers = Message()
                headers["Retry-After"] = "45"
                raise HTTPError("https://provider.example", 429, "limited", headers, None)
            return parse_book(product, book(self.now), self.now)

        feed = PaperMarketFeed(fetch=fetch, clock=lambda: self.now, retry_clock=lambda: now)
        with ThreadPoolExecutor(3) as pool:
            feed.poll(pool)
            self.assertTrue(all(feed.snapshot(self.now)[1].values()))
            throttle = True
            feed.poll(pool)
            self.assertFalse(any(feed.snapshot(self.now)[1].values()))
            count = len(calls)
            now = 144
            feed.poll(pool)
            self.assertEqual(len(calls), count)
            now, throttle = 145, False
            feed.poll(pool)
        self.assertTrue(all(feed.snapshot(self.now)[1].values()))


class LivePaperServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = datetime(2026, 11, 12, 5, tzinfo=timezone.utc)
        self.sol_bid = Decimal("100.00")
        self.depth = "100.0"
        self.sequence = 100
        self.missing = set()
        self.feed = PaperMarketFeed(fetch=self.fetch, clock=lambda: self.now)
        self.session = self.open_session()
        self.addCleanup(lambda: self.session.close())
        self.poll()

    def open_session(self, account=ACCOUNT):
        return LivePaperSession(self.temp.name, account, self.feed, clock=lambda: self.now)

    def fetch(self, product):
        if product in self.missing:
            raise OSError("offline fixture")
        bid = self.sol_bid if product == "SOL-USD" else Decimal("200.00")
        return parse_book(product, book(self.now, str(bid), str(bid + Decimal("0.02")),
                                       self.sequence, self.depth), self.now)

    def poll(self):
        with ThreadPoolExecutor(3) as pool:
            self.feed.poll(pool)

    def move(self, price, seconds=2):
        self.now += timedelta(seconds=seconds)
        self.sequence += 1
        self.sol_bid = Decimal(price)
        self.poll()

    def order(self, **kwargs):
        return {"order_id": "manual_test_order_0001", "symbol": "SOL-USD",
                "side": "BUY", "quantity": "1.50000000", "stop_price": "90", **kwargs}

    def arm(self):
        revision = self.session.state()["risk"]["revision"]
        return self.session.control("arm", expected_revision=revision)

    def restart(self):
        self.session.close()
        self.session = self.open_session()

    def test_manual_fill_replay_independent_pnl_and_sell(self):
        self.assertEqual(self.session.state()["risk"]["reason"], "STARTUP_HALTED")
        self.arm()
        buy = self.session.order(self.order())["fill"]
        self.assertTrue(buy["simulated"])
        self.assertEqual(Decimal(buy["price"]), Decimal("100.02") * Decimal("1.0005"))
        self.assertEqual(Decimal(buy["fee"]), Decimal(buy["price"]) * Decimal("1.5") * Decimal("0.001"))
        self.assertEqual(buy["details"]["source_time"], book(self.now)["time"])
        self.move("104")
        sale = self.session.order({"order_id": "manual_test_order_0002", "symbol": "SOL-USD",
                                   "side": "SELL", "quantity": "0.5"})["fill"]
        self.assertEqual(sale["side"], "SELL")
        before = self.session.state()["portfolio"]
        self.assertEqual(before["positions"], {"SOL-USD": "1.0"})
        self.assertEqual(Decimal(before["nav"]), Decimal(before["cash"]) + Decimal("104"))
        self.assertEqual(Decimal(before["nav"]) - 10000,
                         Decimal(before["realised"]) + Decimal(before["unrealised"]))
        self.assertEqual(Decimal(before["fees"]), Decimal(buy["fee"]) + Decimal(sale["fee"]))
        self.restart()
        self.assertEqual(self.session.state()["portfolio"], before)
        self.assertFalse(self.session.state()["risk"]["armed"])
        self.assertEqual(self.session.order(self.order(quantity="1.5"))["status"], "ALREADY_COMMITTED")
        with self.assertRaisesRegex(PaperRejection, "different terms"):
            self.session.order(self.order(stop_price="91"))

    def test_same_order_concurrently_commits_once(self):
        self.arm()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: self.session.order(self.order()), range(2)))
        self.assertEqual({r["status"] for r in results}, {"SIMULATED_FILL", "ALREADY_COMMITTED"})
        self.assertEqual(len(self.session.runtime.events), 1)

    def test_limit_partial_fill_cancellation_and_restart(self):
        self.arm()
        self.depth = "0.5"
        self.move("101")
        terms = self.order(order_type="LIMIT", limit_price="100.5", quantity="1")
        self.assertEqual(self.session.order(terms)["status"], "PENDING")
        self.move("100")
        self.session.on_market_update()
        order = self.session.order(terms)
        self.assertEqual(order["status"], "PARTIALLY_FILLED")
        self.assertEqual(Decimal(order["order"]["remaining"]), Decimal("0.5"))
        self.assertEqual(self.session.runtime.events[0]["details"]["parent_order_id"], terms["order_id"])
        self.session.on_market_update()
        self.assertEqual(len(self.session.runtime.events), 1)
        self.restart()
        self.assertFalse(self.session.state()["risk"]["armed"])
        self.assertEqual(self.session.cancel({"order_id": terms["order_id"]})["status"], "CANCELLED")
        self.assertEqual(self.session.cancel({"order_id": terms["order_id"]})["status"], "CANCELLED")
        self.arm()
        self.move("99")
        self.session.on_market_update()
        self.assertEqual(len(self.session.runtime.events), 1)
        self.assertEqual(self.session.order(terms)["status"], "CANCELLED")
        self.assertEqual([row["status"] for row in reversed(self.session.state()["order_history"])],
                         ["PENDING", "PARTIALLY_FILLED", "CANCELLED"])

    def test_limit_rejects_full_order_risk_even_with_shallow_depth(self):
        self.arm()
        self.depth = "0.25"
        self.move("100")
        terms = self.order(order_type="LIMIT", limit_price="101", quantity="20")
        result = self.session.order(terms)
        self.assertEqual((result["status"], result["order"]["reason"]), ("REJECTED", "POSITION_RISK_EXCEEDED"))
        self.assertEqual(self.session.order(terms), result)
        self.assertEqual(len(self.session.runtime.events), 0)

    def test_emergency_halt_wins_over_stale_arm(self):
        revision = self.session.state()["risk"]["revision"]
        self.session.control("halt")
        with self.assertRaisesRegex(PaperRejection, "control changed"):
            self.session.control("arm", expected_revision=revision)
        with self.assertRaisesRegex(PaperRejection, "execution is halted"):
            self.session.order(self.order())
        self.restart()
        self.assertFalse(self.session.state()["risk"]["armed"])

    def test_unbounded_depth_cash_stop_and_position_risk_rejected(self):
        self.arm()
        cases = [
            (self.order(stop_price="100"), "protective stop"),
            (self.order(quantity="10"), "position risk exceeded"),
            (self.order(quantity="101"), "top-of-book"),
            (self.order(quantity="100", stop_price="99.99"), "virtual cash"),
            ({"order_id": "manual_test_order_0003", "symbol": "SOL-USD",
              "side": "SELL", "quantity": "1"}, "exceeds the paper position"),
            (self.order(quantity="1e900"), "Invalid quantity"),
            (self.order(proposed_loss="0"), "Invalid order fields"),
        ]
        for order, reason in cases:
            with self.subTest(order=order), self.assertRaisesRegex(PaperRejection, reason):
                self.session.order(order)
        self.assertEqual(len(self.session.runtime.events), 0)

    def test_aggregate_risk_and_stale_quote_fail_closed(self):
        self.arm()
        self.session.order(self.order())
        self.move("160")
        with self.assertRaisesRegex(PaperRejection, "aggregate risk exceeded"):
            self.session.order(self.order(order_id="manual_test_order_0002", quantity="0.25", stop_price="159"))
        self.missing = {"BTC-USD"}
        self.poll()
        self.session.on_market_update()
        self.assertFalse(self.session.state()["risk"]["armed"])
        with self.assertRaisesRegex(PaperRejection, "Fresh books"):
            self.session.order(self.order(order_id="manual_test_order_0003"))
        self.assertEqual(len(self.session.runtime.events), 1)

    def test_protective_stop_uses_gap_bid_and_actual_available_depth(self):
        self.arm()
        self.session.order(self.order())
        self.depth = "0.5"
        self.move("88")
        self.session.on_market_update()
        fills = self.session.state()["fills"]
        self.assertEqual(fills[0]["details"]["origin"], "protective_stop")
        self.assertEqual(Decimal(fills[0]["quantity"]), Decimal("0.5"))
        self.assertLess(Decimal(fills[0]["price"]), Decimal("88"))
        self.session.on_market_update()
        self.assertEqual(len(self.session.runtime.events), 2)
        self.depth = "10"
        self.move("87")
        self.session.on_market_update()
        self.assertEqual(self.session.state()["portfolio"]["positions"], {})

    def test_daily_suspension_survives_recovery_and_same_day_rebound(self):
        self.arm()
        self.session.order(self.order(quantity="60", stop_price="99.95"))
        self.move("95")
        self.session.on_market_update()
        self.assertEqual(self.session.state()["risk"]["reason"], "DAILY_LOSS_HALT")
        self.move("101")
        self.restart()
        with self.assertRaisesRegex(PaperRejection, "loss limit"):
            self.arm()
        self.assertEqual(len(self.session.runtime.events), 1)

    def test_failed_journal_append_halts_and_does_not_mutate_balance(self):
        self.arm()
        cash = self.session.runtime.ledger.cash
        with patch.object(self.session.runtime.journal, "append", side_effect=sqlite3.OperationalError):
            with self.assertRaises(sqlite3.OperationalError):
                self.session.order(self.order())
        self.assertEqual(self.session.runtime.ledger.cash, cash)
        self.assertEqual(self.session.runtime.events, [])
        self.assertTrue(self.session.runtime.ledger.halted)
        self.restart()
        self.assertEqual(self.session.runtime.ledger.cash, cash)

    def test_one_writer_and_owner_binding(self):
        with self.assertRaises(BlockingIOError):
            self.open_session()
        self.session.close()
        try:
            with self.assertRaisesRegex(ValueError, "owner mismatch"):
                self.open_session("different_owner_account")
        finally:
            self.session = self.open_session()

    def test_outage_between_order_checks_requires_manual_rearm(self):
        self.arm()
        healthy = self.session.feed.snapshot(self.now)
        with patch.object(self.session.feed, "snapshot", side_effect=[healthy, ({}, {}, {})]):
            with self.assertRaisesRegex(PaperRejection, "unavailable before fill"):
                self.session.order(self.order())
        self.assertEqual(self.session.runtime.ledger.sequence, 0)
        state = self.session.state()
        self.assertTrue(state["risk"]["data_healthy"])
        self.assertFalse(state["risk"]["armed"])
        self.assertEqual(state["risk"]["reason"], "MARKET_DATA_HALT")
        self.arm()
        self.assertEqual(self.session.order(self.order())["status"], "SIMULATED_FILL")

    def test_future_quote_on_final_order_check_latches_market_data_halt(self):
        self.arm()
        healthy = self.session.feed.snapshot(self.now)
        future = self.now + timedelta(milliseconds=220)
        quotes, health, history = self.session.feed.snapshot(self.now)
        quotes["SOL-USD"] = parse_book("SOL-USD", book(future, sequence=self.sequence + 1), self.now)
        with patch.object(self.session.feed, "snapshot", side_effect=[healthy, (quotes, health, history)]):
            with self.assertRaises(PaperRejection) as denied:
                self.session.order(self.order())
        self.assertEqual(denied.exception.code, "MARKET_DATA_HALT")
        self.assertEqual(self.session.runtime.ledger.sequence, 0)
        self.move("100")
        self.session.on_market_update()
        self.assertFalse(self.session.state()["risk"]["armed"])

    def test_restarted_journal_detects_conflicting_depth_at_the_filled_sequence(self):
        self.arm()
        self.session.order(self.order())
        self.restart()
        quotes, healthy, history = self.session.feed.snapshot(self.now)
        quotes["SOL-USD"] = replace(quotes["SOL-USD"], ask_size=quotes["SOL-USD"].ask_size + 1)
        with patch.object(self.session.feed, "snapshot", return_value=(quotes, healthy, history)):
            state = self.session.state()
            self.assertFalse(state["risk"]["data_healthy"])
            self.assertFalse(state["risk"]["can_arm"])
        self.assertEqual(self.session.runtime.ledger.sequence, 1)


if __name__ == "__main__":
    unittest.main()
