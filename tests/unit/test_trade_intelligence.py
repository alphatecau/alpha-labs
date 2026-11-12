"""Causal, read-only acceptance cases for Trade Intelligence v1."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from email.message import Message
from email.utils import format_datetime
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from alpha_lab.data.adapters.coinbase_candles import (
    SEALED_END, SEALED_START, SOURCE, CandleBatch, ProductRules, fetch_candles, latest_candle_end,
    parse_candles, parse_product,
)
from alpha_lab.data.csv_import import Bar
from alpha_lab.data.public_https import decode_public_json
from alpha_lab.research.coinbase_paper_book import PRODUCTS, parse_book
from alpha_lab.research.trade_intelligence import Evidence, OFFLINE, analyse_trade_intelligence
from alpha_lab.research.trade_market_feed import TradeCandleFeed, retry_delay
from alpha_lab.research.trade_risk import ResearchRisk, size_long
from alpha_lab.research.trade_signals import STRATEGIES, classify_regime, generate_signals
from alpha_lab.research.trade_walk_forward import _trade, walk_forward

NOW = datetime(2026, 11, 12, 15, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)
END = latest_candle_end(NOW, "4h")
SYMBOL = "BTC-USD"


def trend_bars(*, end=END, step=timedelta(hours=4), count=64, change=D("0.25")):
    start = end - count * step
    bars = []
    for i in range(count):
        price = D(100) + change * i
        spread = D("0.80")
        bars.append(Bar(start + i * step, price, price + spread, price - spread, price, D("4")))
    return tuple(bars)


def candle_batch(product=SYMBOL, now=NOW, *, source=SOURCE, change=D("0.25")):
    end = latest_candle_end(now, "4h")
    return CandleBatch(product, "4h", trend_bars(end=end, change=change), end, "a" * 64, source)


def book(product=SYMBOL, now=NOW, *, event=None, ask=None, depth="1000"):
    ask = ask if ask is not None else trend_bars()[-1].close
    return parse_book(product, {"auction_mode": False, "sequence": 7,
                               "time": (event or now).isoformat().replace("+00:00", "Z"),
                               "bids": [[str(ask - D("0.02")), depth, 1]],
                               "asks": [[str(ask), depth, 1]]}, now)


def rules(product=SYMBOL):
    return ProductRules(product, D("0.01"), D("0.001"), D("1"))


def portfolio(**kwargs):
    return replace(ResearchRisk(D(10000), D(10000), D(10000), D(10000), D(10000), D(0), ()),
                   **kwargs)


def payload(start, count):
    return [[int((start + i * HOUR).timestamp()), "99", "102", "100.123456789012345678", "101", "12"]
            for i in range(count)]


class CoinbaseCandleTests(TestCase):
    def setUp(self):
        self.start = END - timedelta(hours=8)

    def parse(self, rows):
        return parse_candles(rows, start=self.start, end=END, timeframe="4h")

    def test_closed_candles_are_sorted_aggregated_and_exclude_current_bar(self):
        rows = payload(self.start, 9)
        rows[-1][1:] = ["100000", "1", "99", "1", "-8"]
        bars = self.parse(list(reversed(rows)))
        self.assertEqual([bar.time for bar in bars], [self.start, self.start + timedelta(hours=4)])
        self.assertEqual(bars[0].open, D("100.123456789012345678"))
        self.assertEqual(bars[0].close, D(101))
        self.assertEqual(bars[0].volume, D(48))

    def test_invalid_duplicate_missing_outlier_and_nonfinite_data(self):
        original = payload(self.start, 8)
        for invalid in (original[:-1], [*original, original[0]], [[True, *original[0][1:]], *original[1:]],
                        [[original[0][0], "1", "101", "100", "101", "1"], *original[1:]],
                        [[original[0][0], "99", "101", "100", "NaN", "1"], *original[1:]],
                        [[original[0][0], "99", "101", "100", "100", "1e-9999"], *original[1:]]):
            with self.subTest(invalid=invalid[0]), self.assertRaises(ValueError):
                self.parse(invalid)

    def test_exact_numeric_json_and_duplicate_fields(self):
        self.assertEqual(decode_public_json(b"[1.123456789012345678]", parse_float=D),
                         [D("1.123456789012345678")])
        with self.assertRaises(ValueError):
            decode_public_json(b'{"x":1,"x":2}', parse_float=D)

    def test_utc_publication_delay_and_reserved_period(self):
        self.assertEqual(latest_candle_end(END + timedelta(seconds=59), "4h"), END - 4 * HOUR)
        self.assertEqual(latest_candle_end(END + timedelta(minutes=1), "4h"), END)
        self.assertEqual(latest_candle_end(NOW.astimezone(timezone(timedelta(hours=10))), "4h"), END)
        with self.assertRaises(ValueError):
            latest_candle_end(NOW.replace(tzinfo=None), "4h")
        opener = Mock()
        for start, end in ((SEALED_START - HOUR, SEALED_START + HOUR),
                           (SEALED_END - HOUR, SEALED_END + HOUR)):
            with self.assertRaisesRegex(ValueError, "reserved"):
                fetch_candles(SYMBOL, start=start, end=end, timeframe="1h", opener=opener)
        opener.assert_not_called()

    def test_venue_precision_and_market_flags(self):
        data = {"id": SYMBOL, "base_currency": "BTC", "quote_currency": "USD", "status": "online",
                "quote_increment": "0.01", "base_increment": "0.001", "min_market_funds": "1",
                "cancel_only": False, "post_only": False, "limit_only": False, "auction_mode": False}
        self.assertEqual(parse_product(SYMBOL, data), rules())
        for bad in ({"quote_currency": "USDT"}, {"base_increment": "0"}, {"auction_mode": True},
                    {"min_market_funds": None}, {"limit_only": True}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_product(SYMBOL, data | bad)

    def test_rate_limit_fail_closed_and_respects_retry_after(self):
        headers = Message()
        headers["Retry-After"] = format_datetime(NOW + timedelta(minutes=3), usegmt=True)
        error = HTTPError("https://api.exchange.coinbase.com", 429, "rate limit", headers, None)
        self.assertEqual(retry_delay(error, NOW), 180)
        now = [NOW]
        fetch = Mock(side_effect=[error, *[candle_batch(s) for s in PRODUCTS]])
        feed = TradeCandleFeed(fetch=fetch, fetch_rules=rules, clock=lambda: now[0])
        feed.poll()
        self.assertEqual(feed.snapshot(NOW), ({}, {}, "PROVIDER_RATE_LIMITED"))
        now[0] += timedelta(seconds=179)
        feed.poll()
        self.assertEqual(fetch.call_count, 1)
        now[0] += timedelta(seconds=1)
        feed.poll()
        self.assertEqual(set(feed.snapshot(now[0])[0]), set(PRODUCTS))
        self.assertFalse(feed.snapshot(END + 5 * HOUR)[0])


class SignalAndRiskTests(TestCase):
    def test_trend_range_and_volatility_are_explainable(self):
        upward = trend_bars()
        downward = trend_bars(change=D("-0.25"))
        ranged = trend_bars(change=D(0))
        for bars, expected in ((upward, "TRENDING_UP"), (downward, "TRENDING_DOWN"), (ranged, "RANGE_BOUND")):
            with self.subTest(expected=expected):
                regime, signals = generate_signals(bars)
                self.assertEqual(regime.trend, expected)
                self.assertEqual(tuple(s.strategy for s in signals), STRATEGIES)
                self.assertTrue(regime.reasons)
        for width, volatility in ((D("1.60"), "HIGH"), (D("0.10"), "LOW")):
            changed = (*ranged[:-14], *(replace(b, high=b.close + width, low=b.close - width) for b in ranged[-14:]))
            self.assertEqual(classify_regime(changed).volatility, volatility)
        unstable = (*ranged[:-1], replace(ranged[-1], high=D(110), low=D(90)))
        self.assertEqual(classify_regime(unstable).trend, "UNCERTAIN")

    def test_prior_channel_excludes_breakout_candle(self):
        bars = trend_bars()
        last = replace(bars[-1], close=D("118"), high=D("118"))
        regime, signals = generate_signals((*bars[:-1], last))
        self.assertLess(regime.channel_high, last.close)
        self.assertEqual(signals[2].direction, "LONG")

    def plan(self, **kw):
        defaults = dict(quote=book(), rules=rules(), regime=classify_regime(trend_bars()),
                        risk=portfolio(), now=NOW, signal_at=END, interval_seconds=14400)
        return size_long(**(defaults | kw))

    def test_decimal_position_size_after_costs_and_precision(self):
        plan, reasons = self.plan()
        self.assertFalse(reasons)
        self.assertGreater(D(plan["max_quantity"]), D(0))
        self.assertEqual(D(plan["max_quantity"]) % rules().quantity_step, D(0))
        self.assertEqual(D(plan["stop"]) % rules().price_step, D(0))
        self.assertLess(D(plan["stop"]), book().bid)
        self.assertGreater(D(plan["target"]), D(plan["entry"]))
        self.assertLessEqual(D(plan["planned_loss_fraction_post_entry"]), D(".0025"))
        self.assertGreaterEqual(D(plan["reward_to_risk_net"]), D("1.5"))
        self.assertEqual(plan["max_holding_seconds"], 86400)

    def test_independent_halts_and_exposure_limits(self):
        cases = (
            (portfolio(halt_reason="OPERATOR_HALT"), "OPERATOR_HALT"),
            (portfolio(open_stop_risk=D(100)), "Aggregate stop-risk limit"),
            (portfolio(cash=D(6500), exposure=((SYMBOL, D(3500)),)), "Asset concentration limit"),
            (portfolio(cash=D(3000), exposure=(("ETH-USD", D(3500)), ("SOL-USD", D(3500)))),
             "Correlated crypto exposure limit"),
            (portfolio(nav=D(9800), cash=D(9800)), "Daily loss or drawdown HALT"),
            (portfolio(nav=D(9500), cash=D(9500), day_start_nav=D(9500)), "Daily loss or drawdown HALT"),
        )
        for risk, expected in cases:
            with self.subTest(expected=expected):
                plan, reasons = self.plan(risk=risk)
                self.assertIsNone(plan)
                self.assertIn(expected, reasons)

    def test_failed_precision_stale_future_chase_and_insufficient_cash(self):
        cases = (
            {"rules": replace(rules(), min_notional=D("10000"))},
            {"regime": replace(classify_regime(trend_bars()), atr=D(1))},
            {"quote": book(event=NOW - timedelta(seconds=11), now=NOW - timedelta(seconds=11))},
            {"quote": book(event=NOW + timedelta(milliseconds=100))},
            {"quote": book(ask=D("125"))},
            {"risk": portfolio(cash=D("0.20"), exposure=(("ETH-USD", D("9999.80")),))},
            {"signal_at": END - 4 * HOUR},
            {"risk": None},
        )
        for inputs in cases:
            with self.subTest(inputs=inputs):
                plan, reasons = self.plan(**inputs)
                self.assertIsNone(plan)
                self.assertTrue(reasons)

    def engine(self, **inputs):
        defaults = dict(now=NOW, quotes={p: book(p) for p in PRODUCTS}, healthy=dict.fromkeys(PRODUCTS, True),
                        batches={p: candle_batch(p) for p in PRODUCTS}, rules={p: rules(p) for p in PRODUCTS},
                        risk=portfolio())
        return analyse_trade_intelligence(**(defaults | inputs))

    def test_market_screen_rejects_unverified_and_spot_shorts(self):
        result = self.engine(batches={p: candle_batch(p, change=D("-0.25") if p == "ETH-USD" else D("0.25"))
                                      for p in PRODUCTS})
        self.assertEqual(result["decision"], "NO TRADE")
        self.assertFalse(result["ranking"])
        self.assertFalse(result["automated_paper_execution"])
        self.assertEqual(result["markets"][0]["decision"], "UNVERIFIED")
        self.assertEqual(result["markets"][1]["decision"], "UNSUPPORTED")
        self.assertEqual(result["markets"][0]["candidates"][0]["committee"]["mode"], "DETERMINISTIC_ADVISORY")
        self.assertTrue(all(c["plan"] is None for m in result["markets"] for c in m["candidates"]))

    def test_books_fail_closed_and_replay_never_becomes_live(self):
        scenarios = ({"healthy": {}}, {"quotes": {p: book(p, event=NOW + timedelta(milliseconds=100))
                                               for p in PRODUCTS}},
                     {"batches": {p: candle_batch(p, source="Synthetic fixture") for p in PRODUCTS}},
                     {"provider_state": "PROVIDER_RATE_LIMITED"})
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                self.assertTrue(all(m["decision"] == "HALT" for m in self.engine(**scenario)["markets"]))
        self.assertEqual(self.engine(mode=OFFLINE)["decision"], "NO TRADE")

    def test_strong_metrics_still_require_existing_promotion_authority(self):
        record = Evidence(SYMBOL, "4h", "ema-trend", "1.0", "LONG", "TRENDING_UP", "NORMAL",
                          NOW - timedelta(days=120), NOW - timedelta(days=10), "same benchmark",
                          SOURCE, D(40), 50, 10, 8, .03, .001, .001, .01, .001)
        rejected = self.engine(evidence=(record,))
        self.assertEqual(rejected["decision"], "NO TRADE")
        self.assertIn("Independent archive", rejected["markets"][0]["candidates"][0]["validation_reasons"][0])
        with patch("alpha_lab.research.trade_intelligence.decide_strategy_promotion",
                   return_value={"promotion_authorised": True}):
            # Simulates a future independent research approval, never a deployed authority.
            peer = replace(record, product="ETH-USD", adjusted_lower_per_bar=.002)
            accepted = self.engine(evidence=(record, peer))
            self.assertEqual([r["product"] for r in accepted["ranking"]], ["ETH-USD", "BTC-USD"])
            blocked = self.engine(evidence=(record,), risk=portfolio(halt_reason="OPERATOR_HALT"))
            self.assertEqual(blocked["decision"], "NO TRADE")
            self.assertEqual(blocked["markets"][0]["candidates"][0]["decision"], "HALT")
            self.assertFalse(accepted["automated_paper_execution"])
            self.assertFalse(accepted["real_money_execution"])


class WalkForwardTests(TestCase):
    def test_embargo_replay_and_sealed_period_guard(self):
        bars = trend_bars(end=END, step=HOUR, count=640, change=D("0.06"))
        result = walk_forward(SYMBOL, bars, source="Synthetic fixture", capture_sha256="a" * 64)
        self.assertEqual(result, walk_forward(SYMBOL, bars, source="Synthetic fixture", capture_sha256="a" * 64))
        self.assertEqual(result["source"], "Synthetic fixture")
        self.assertEqual(len(result["fold_windows"]), 2)
        first, second = result["fold_windows"]
        self.assertEqual(datetime.fromisoformat(second[0]) - datetime.fromisoformat(first[1]), 24 * HOUR)
        self.assertFalse(result["promotion_authorised"])
        self.assertGreater(result["comparisons"][0]["trades"], 0)
        with self.assertRaisesRegex(ValueError, "reserved"):
            walk_forward(SYMBOL, trend_bars(end=SEALED_START + 48 * HOUR, step=HOUR, count=640),
                         source="Synthetic fixture", capture_sha256="a" * 64)

    def test_same_hour_stop_target_collision_is_adverse(self):
        regime = classify_regime(trend_bars())
        entry = regime.close
        bar = Bar(NOW, entry, entry + 4, entry - 4, entry, D(10))
        trade = _trade((bar,), 0, regime, "LONG")
        self.assertEqual(trade.marks, (entry - D("1.5") * regime.atr,))
        self.assertLess(trade.liquidation_path(D(40))[-1], trade.liquidation_path(D(20))[-1])
