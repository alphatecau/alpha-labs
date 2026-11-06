from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
import unittest

from alpha_lab.data.csv_import import Bar
from alpha_lab.research.spot_followup_signals import TrendObservation, rotation_signals, trend_observations
from alpha_lab.research.strategies.regime_trend import Regime, Signal
from alpha_lab.research.strategies.registered_spot import Decision
from alpha_lab.research.strategy_v09_followup import cost_scenarios, drawdown_duration

D = Decimal


class FollowupTests(unittest.TestCase):
    def test_fixed_fee_and_total_round_trip(self):
        cases = cost_scenarios(D(10))
        self.assertEqual(tuple(cases), (20, 40, 60, 80))
        for bps, model in cases.items():
            self.assertEqual(model.fee_bps, 10)
            price = D(10_000)
            self.assertEqual(model.buy_outlay(D(1), price) - model.sell_proceeds(D(1), price), bps)

    def test_partial_daily_close_and_nonoverlapping_volatility_filter(self):
        start = datetime(2025, 1, 1, tzinfo=UTC)
        bars = [Bar(start + timedelta(hours=i), D(100), D(120), D(90), D(100 if i < 743 else 110), D(1))
                for i in range(748)]
        observations = [Signal(Regime.UP, D("0.02"), D("0.01"), True)] * len(bars)
        observations[747] = Signal(Regime.UP, D("0.02"), D("0.015"), True)
        params = SimpleNamespace(volatility_hours=72, entry_momentum_fraction=D("0.01"))
        events = trend_observations(bars, observations, params, D("0.04"))
        self.assertFalse(events[739].long.enter)
        self.assertIsNone(events[742])
        self.assertTrue(events[743].long.enter)
        self.assertEqual(events[747].regime, Regime.HIGH_VOL)
        self.assertFalse(events[747].long.enter)
        self.assertEqual(events[:743], trend_observations(bars[:743], observations[:743], params, D("0.04")))

    def test_rotation_respects_eligibility_and_stable_ties(self):
        a = TrendObservation(Regime.UP, D("0.02"), Decision(True, False, D("0.04")), False)
        b = TrendObservation(Regime.DOWN, D("0.03"), Decision(False, True, D("0.04")), False)
        streams = rotation_signals({"BTC": (None, a, b, b), "ETH": (None, a, a, b)})
        self.assertEqual(streams["BTC"], (None, a.long, b.long, b.long))
        self.assertEqual(streams["ETH"], (None, b.long, a.long, b.long))

    def test_duration_resets_at_recovered_peak(self):
        self.assertEqual(drawdown_duration([97, 98, 100, 102, 101, 99, 98], 100), 3)
        self.assertEqual(drawdown_duration([100, 100, 101], 100), 0)
