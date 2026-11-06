from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from alpha_lab.backtest.costs import CostModel
from alpha_lab.data.csv_import import Bar
from alpha_lab.research.spot_evidence import performance
from alpha_lab.research.spot_portfolio import Portfolio, ReplayRules, replay_portfolio
from alpha_lab.research.spot_reference import ReferenceAudit
from alpha_lab.research.strategies.registered_spot import Decision, aggregate, strategy_signals, timeframes
from alpha_lab.research.strategy_v08_replay import RiskLimits
from alpha_lab.research.strategy_v09 import evaluation_windows, load_registry

D = Decimal
ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "configs/strategy-v0.9.json"
DAY_START = datetime(2025, 1, 6, tzinfo=UTC)
COSTS = CostModel()
LIMITS = RiskLimits(D("0.04"), D("0.0025"), D("0.01"), D("0.02"), D("0.05"))
RULES = ReplayRules(D(10_000), D("0.20"), LIMITS)
LONG = Decision(True, False, D("0.05"))


def bars(count, start=DAY_START, variations=None):
    variations = variations or {}
    return tuple(Bar(start + timedelta(hours=i), *map(D, variations.get(i, (100, 101, 99, 100))), D(1))
                 for i in range(count))


class TestRegisteredSignals(unittest.TestCase):
    def setUp(self):
        self.config = load_registry(REGISTRY)
        self.timing = self.config["signals"]

    def test_partial_utc_windows_are_ignored(self):
        data = bars(174, DAY_START - timedelta(hours=3))
        four = list(aggregate(data, 4))
        week, = aggregate(data, 168)
        self.assertEqual((four[0][0], four[0][1].time, four[0][1].volume), (6, DAY_START, D(4)))
        self.assertEqual((week[0], week[1].time, week[1].volume), (170, DAY_START, D(168)))
        with self.assertRaisesRegex(ValueError, "incomplete"):
            tuple(aggregate(data[:10] + data[11:], 24))

    def test_breakout_requires_completed_daily_confirmation_and_uses_prior_high(self):
        params = {**self.config["candidates"][0], "confirmation_bars": 2}
        data = bars(100, variations={91: (100, 111, 99, 110), 95: (100, 121, 99, 120)})
        signals = strategy_signals(timeframes(data), len(data), params, self.timing)
        self.assertFalse(signals[91].enter)
        self.assertIsNone(signals[94])
        self.assertTrue(signals[95].enter)
        self.assertFalse(signals[95].exit)
        self.assertGreater(signals[95].stop_fraction, D("0.01"))
        self.assertEqual(signals[:95], strategy_signals(timeframes(data[:95]), 95, params, self.timing))

    def test_mean_reversion_blocks_directional_daily_moves(self):
        params = self.config["candidates"][4]
        flat_data = bars(288, variations={275: (100, 101, 89, 90)})
        downward_data = bars(288, variations={263: (100, 101, 89, 90), 275: (100, 101, 89, 90)})
        flat = strategy_signals(timeframes(flat_data), len(flat_data), params, self.timing)
        down = strategy_signals(timeframes(downward_data), len(downward_data), params, self.timing)
        self.assertTrue(flat[275].enter)
        self.assertTrue(flat[279].exit)
        self.assertFalse(down[275].enter)
        self.assertTrue(down[275].exit)

    def test_registry_mutation_is_rejected(self):
        with TemporaryDirectory() as directory:
            changed = Path(directory) / "changed.json"
            changed.write_bytes(REGISTRY.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "frozen"):
                load_registry(changed)

    def test_registered_fold_gaps_and_tail(self):
        protocol = self.config["protocol"]
        data = bars(24_144, datetime.fromisoformat(protocol["first_open_utc"]))
        periods, folds = evaluation_windows(data, protocol)
        self.assertEqual(len(folds), 14)
        self.assertEqual(periods["validation"][0] - periods["development"][1], 48)
        self.assertEqual(periods["test_unsealed"][0] - periods["validation"][1], 48)
        self.assertEqual(folds[-1][1], len(data))
        self.assertTrue(all(b[0] - a[1] == 48 for a, b in zip(folds, folds[1:])))


class TestSharedReplay(unittest.TestCase):
    def single(self, data, events, *, start=1, rules=RULES):
        prices, signals = {"BTC": data}, {"BTC": events}
        result = replay_portfolio(prices, signals, start, len(data), rules, COSTS)
        ReferenceAudit().replay(prices, signals, start, len(data), rules, COSTS, result)
        return result

    def test_shared_admission_counts_reserved_stop_risk(self):
        data = bars(4)
        markets = {"BTC": data, "ETH": data}
        signals = {symbol: (LONG, None, None, None) for symbol in markets}
        rules = replace(RULES, limits=replace(LIMITS, aggregate_stop_risk=D("0.003")))
        result = replay_portfolio(markets, signals, 1, 4, rules, COSTS)
        self.assertEqual([fill.symbol for fill in result.fills], ["BTC", "ETH"])
        self.assertLess(result.fills[1].planned_risk, result.fills[0].planned_risk)
        self.assertLessEqual(result.max_planned_risk, D("0.003"))
        self.assertGreater(result.cash, 0)
        metrics = performance(markets, result, 4)
        self.assertAlmostEqual(metrics["gross_fixed_fills_return_pct"], 0.0, places=20)
        self.assertLess(metrics["net_execution_return_pct"], 0)
        self.assertEqual(metrics["terminal_open_positions"], 2)
        ReferenceAudit().replay(markets, signals, 1, 4, rules, COSTS, result)

    def test_previous_fill_friction_counts_towards_the_next_admission(self):
        state = Portfolio(RULES, COSTS.twice())
        state.cash = D("9501")
        prices = {"BTC": D(100), "ETH": D(100)}
        state.enter(1, "BTC", LONG, prices)
        self.assertLess(state.mark(prices)[0], D("9500"))
        state.enter(1, "ETH", LONG, prices)
        self.assertEqual([fill.symbol for fill in state.fills], ["BTC"])

    def test_stop_gap_uses_worse_open(self):
        data = bars(4, variations={2: (88, 91, 87, 90)})
        result = self.single(data, (LONG, None, None, None))
        entry, exit_ = result.fills
        self.assertEqual((exit_.index, exit_.reason, exit_.reference_price), (2, "STOP_GAP", 88))
        self.assertGreater(-result.closed[0].net_pnl, entry.planned_risk)

    def test_touched_stop_exits_even_when_close_recovers(self):
        data = bars(4, variations={1: (100, 102, 94, 101)})
        result = self.single(data, (LONG, None, None, None))
        self.assertEqual((result.fills[-1].reason, result.fills[-1].reference_price), ("STOP_TOUCH", 95))
        self.assertEqual(result.closed[0].hours_held, 1)

    def test_delay_and_holding_timer_use_entry_open(self):
        data = bars(8)
        rules = replace(RULES, signal_delay_hours=1, maximum_holding_hours=2, cooldown_hours=2)
        result = self.single(data, (None, LONG, LONG, LONG, LONG, LONG, None, None), start=2, rules=rules)
        self.assertEqual([(r.index, r.reason) for r in result.fills], [(3, "SIGNAL"), (5, "TIME_LIMIT"), (7, "SIGNAL")])

    def test_close_breach_flattens_after_utc_day_rolls(self):
        data = bars(27, variations={23: (100, 101, 79, 80), 24: (80, 81, 79, 80)})
        decision = Decision(True, False, D("0.01"))
        rules = replace(RULES, close_triggered_stop=True)
        result = self.single(data, (decision,) * len(data), rules=rules)
        self.assertEqual([(r.index, r.reason) for r in result.fills[:3]], [(1, "SIGNAL"), (24, "DAILY_LOSS"), (25, "SIGNAL")])
        self.assertGreaterEqual(result.daily_suspensions, 1)

    def test_portfolio_drawdown_halts_for_window_and_can_overshoot(self):
        data = bars(26, variations={1: (100, 101, "99.1", 100), 2: (45, 46, 44, 45)})
        decision = Decision(True, False, D("0.01"))
        result = self.single(data, (decision,) * len(data))
        self.assertEqual([r.reason for r in result.fills], ["SIGNAL", "PORTFOLIO_DRAWDOWN"])
        self.assertGreater(result.max_drawdown, LIMITS.drawdown)
        self.assertTrue(result.window_suspended)

    def test_reference_rejects_tampered_fill(self):
        data = bars(4)
        events = (LONG, None, None, None)
        result = self.single(data, events)
        result.fills[0] = replace(result.fills[0], fee=D(0))
        with self.assertRaisesRegex(ValueError, "fill mismatch"):
            ReferenceAudit().replay({"BTC": data}, {"BTC": events}, 1, 4, RULES, COSTS, result)


if __name__ == "__main__":
    unittest.main()
