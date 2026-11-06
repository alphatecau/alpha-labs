"""Offline v0.8 unit and archive-to-report integration tests."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
import runpy
from statistics import stdev
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from archive_fixture import two_month_transport
from alpha_lab.backtest.costs import CostModel
from alpha_lab.data.adapters.binance_archive import build_dataset
from alpha_lab.data.csv_import import Bar, Dataset, load_csv
from alpha_lab.research.multiple_testing import moving_block_lower_bound, paired_daily_excess_bps
from alpha_lab.research.strategies.regime_trend import Regime, classify, momentum_signals
from alpha_lab.research.strategy_v08 import COMPARATORS, evaluate_market, load_study, run_study
from alpha_lab.research.strategy_v08_replay import replay_window

D = Decimal
REGISTRY = Path(__file__).resolve().parents[2] / "configs" / "strategy-v0.8.json"
STUDY = load_study(REGISTRY)
START = datetime(2025, 1, 1, tzinfo=UTC)


def bars_from_prices(prices, start=START):
    return tuple(Bar(start + timedelta(hours=i), D(o), max(D(o), D(c)),
                     min(D(o), D(c)), D(c), D(1)) for i, (o, c) in enumerate(prices))


class MomentumTests(unittest.TestCase):
    def test_regime_boundaries_and_conflicting_signals(self):
        params = STUDY.parameters
        cases = [
            ("0.005", "0.01", "0", Regime.UP),
            ("-0.005", "-0.01", "0", Regime.DOWN),
            ("0.00499", "0.01", "0", Regime.RANGE),
            ("0.02", "0", "0", Regime.UNCERTAIN),
            ("-0.02", "0.01", "0", Regime.UNCERTAIN),
            ("0.02", "0.01", "0.015", Regime.HIGH_VOL),
        ]
        for spread, slope, vol, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(classify(D(spread), D(slope), D(vol), params), expected)

    def test_momentum_and_volatility_match_direct_calculation(self):
        closes = [D(100) + D(i) / 4 + D(i % 5) / 10 for i in range(200)]
        params = STUDY.parameters
        signals = momentum_signals(closes, params)
        self.assertEqual(signals[143].regime, Regime.UNCERTAIN)
        self.assertFalse(signals[143].target_long)
        self.assertTrue(signals[144].target_long)
        self.assertEqual(signals[-1].momentum, closes[-1] / closes[-73] - 1)
        returns = [closes[i] / closes[i - 1] - 1 for i in range(128, 200)]
        self.assertAlmostEqual(float(signals[-1].hourly_volatility), float(stdev(returns)), places=15)

    def test_high_volatility_downtrend_and_range_target_flat(self):
        series = (
            ([D(100)] * 180, Regime.RANGE),
            ([D(300 - i) for i in range(180)], Regime.DOWN),
            ([D(100 + 50 * (i % 2)) for i in range(180)], Regime.HIGH_VOL),
        )
        for closes, expected in series:
            with self.subTest(regime=expected):
                last = momentum_signals(closes, STUDY.parameters)[-1]
                self.assertEqual(last.regime, expected)
                self.assertFalse(last.target_long)

    def test_weak_positive_momentum_in_uptrend_targets_flat(self):
        params = replace(STUDY.parameters, entry_momentum_fraction=D("0.10"))
        closes = [D(100) + D(i) / 10 for i in range(180)]
        last = momentum_signals(closes, params)[-1]
        self.assertEqual(last.regime, Regime.UP)
        self.assertFalse(last.target_long)

    def test_prefix_invariant_and_invalid_inputs(self):
        prices = [D(100) + D(i) / 4 for i in range(200)]
        old = momentum_signals(prices, STUDY.parameters)
        changed = prices[:165] + [close * 2 for close in prices[165:]]
        self.assertEqual(momentum_signals(changed, STUDY.parameters)[:165], old[:165])
        self.assertEqual(momentum_signals(prices[:165], STUDY.parameters), old[:165])
        for invalid in ([], [D("NaN")], [D(0)], [None]):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                momentum_signals(invalid, STUDY.parameters)
        for param in ({"fast_hours": True}, {"fast_hours": 120}, {"volatility_hours": 721},
                      {"entry_momentum_fraction": D("Infinity")}):
            with self.subTest(param=param), self.assertRaises(ValueError):
                replace(STUDY.parameters, **param)


class ReplayTests(unittest.TestCase):
    def replay(self, prices, targets=None, *, risk=STUDY.risk, costs=STUDY.costs, start=START):
        bars = bars_from_prices(prices, start)
        return replay_window(bars, targets or [True] * len(bars), 1, len(bars),
                             capital=STUDY.capital, allocation=STUDY.allocation,
                             costs=costs, risk=risk)

    def test_signal_at_close_changes_next_open_and_ignores_same_bar_close_for_fill(self):
        prices = [(100, 100), (100, 110), (120, 116), (125, 124)]
        targets = [False, True, False, False]
        result = self.replay(prices, targets)
        self.assertEqual([order["side"] for order in result.orders], ["BUY", "SELL"])
        self.assertEqual([order["time"].hour for order in result.orders], [2, 3])
        self.assertEqual(result.orders[1]["reason"], "SIGNAL_FLAT")
        changed = prices[:2] + [(120, 700), (125, 50)]
        self.assertEqual(self.replay(changed, targets).orders[0], result.orders[0])
        self.assertEqual(self.replay(prices, targets), result)

    def test_fee_slippage_and_trade_accounting_against_hand_calculation(self):
        prices = [(100, 100), (100, 100), (110, 110), (110, 110)]
        replay = self.replay(prices, [True, False, False, False], risk=None)
        units = D(2000) / (D("100.10") * D("1.001"))
        proceeds = units * D("109.89") * D("0.999")
        fees = units * (D("100.10") + D("109.89")) * D("0.001")
        slippage = units * (D("0.10") + D("0.11"))
        self.assertAlmostEqual(replay.nav[-1], D(8000) + proceeds, places=21)
        self.assertAlmostEqual(D(replay.metrics["modelled_fees_usdt"]), fees, places=21)
        self.assertAlmostEqual(D(replay.metrics["modelled_slippage_usdt"]), slippage, places=21)
        self.assertAlmostEqual(replay.metrics["expectancy_usdt_per_closed_trade"], float(proceeds - D(2000)))
        self.assertIsNone(replay.metrics["profit_factor"])
        stress = self.replay(prices, [True, False, False, False], risk=None, costs=CostModel(D(20), D(20)))
        self.assertLess(stress.nav[-1], replay.nav[-1])

    def test_planned_stop_risk_and_gap_at_next_open(self):
        prices = [(100, 100), (100, 96), (80, 80), (80, 80)]
        result = self.replay(prices)
        buy, sell = result.orders[:2]
        self.assertEqual(sell["reason"], "STOP_AT_CLOSE")
        self.assertEqual(sell["time"].hour, 2)
        planned = -buy["cash_delta"] - STUDY.costs.sell_proceeds(buy["quantity"], D(96))
        self.assertAlmostEqual(planned, D(25), places=20)
        self.assertLessEqual(buy["planned_stop_risk_fraction"], D("0.0025"))
        self.assertLess(sell["cash_delta"] + buy["cash_delta"], -planned)
        half = self.replay(prices, risk=STUDY.half_risk)
        self.assertAlmostEqual(half.orders[0]["quantity"] * 2, buy["quantity"], places=20)

    def test_daily_suspension_rejects_until_next_utc_day(self):
        prices = [(100, 100), (100, 100), (100, 50), (45, 45), (45, 45), (45, 45)]
        result = self.replay(prices, start=START + timedelta(hours=19))
        self.assertEqual(result.orders[1]["reason"], "DAILY_LOSS_LIMIT")
        self.assertEqual(result.orders[-1]["time"].hour, 0)
        self.assertEqual(result.metrics["risk"]["entry_rejections"]["DAILY_LOSS_LIMIT"], 1)
        self.assertEqual(result.metrics["risk"]["daily_suspensions"], 1)

    def test_drawdown_suspension_latches_across_day_boundary(self):
        prices = [(100, 100), (100, 100), (100, 5), (5, 5), (5, 5), (5, 5)]
        result = self.replay(prices, start=START + timedelta(hours=20))
        self.assertEqual([order["side"] for order in result.orders], ["BUY", "SELL"])
        self.assertEqual(result.orders[1]["reason"], "DRAWDOWN_LIMIT")
        self.assertTrue(result.metrics["risk"]["drawdown_suspension"])
        self.assertEqual(result.metrics["risk"]["entry_rejections"]["DRAWDOWN_LIMIT"], 2)
        with self.assertRaisesRegex(ValueError, "position_stop_risk"):
            replace(STUDY.risk, position_stop_risk=D("0.00251"))

    def test_flat_boundary_statistics(self):
        flat = self.replay([(100, 100)] * 3, [False] * 3, risk=None)
        self.assertEqual(flat.nav[-1], D(10_000))
        self.assertIsNone(flat.metrics["profit_factor"])
        self.assertIsNone(flat.metrics["expectancy_usdt_per_closed_trade"])
        self.assertIsNone(flat.metrics["sharpe_zero_risk_free"])
        with self.assertRaises(ValueError):
            self.replay([(100, 100)])


class StudyTests(unittest.TestCase):
    def test_bootstrap_uses_complete_days_and_replays_the_same_seed(self):
        bars = bars_from_prices([(100, 100)] * 51, START + timedelta(hours=21))
        excess = paired_daily_excess_bps(bars, [D(10000 + i) for i in range(51)],
                                         [D(10000)] * 51, D(10000), D(0))
        self.assertEqual(excess, [24.0, 24.0])
        config = dict(block_days=2, minimum_blocks=2, replicates=100, seed=808,
                      family_alpha=.05, comparisons=9)
        self.assertIsNone(moving_block_lower_bound(excess, **config)["lower_daily_excess_bps"])
        sample = [1, 2, 3, 4, 5]
        self.assertEqual(moving_block_lower_bound(sample, **config), moving_block_lower_bound(sample, **config))
        self.assertEqual(moving_block_lower_bound([24] * 4, **config)["lower_daily_excess_bps"], 24)

    def test_missing_duplicate_and_non_utc_timestamps_fail_before_replay(self):
        bars = bars_from_prices([(100, 100)] * 1488)
        dataset = Dataset(bars, "USDT", "fixture-only", "synthetic", 60)
        for invalid in (bars[:1000] + bars[1001:], bars[:1000] + (bars[999],) + bars[1001:],
                        (replace(bars[0], time=START.replace(tzinfo=None)),) + bars[1:]):
            with self.assertRaisesRegex(ValueError, "ordered UTC"):
                evaluate_market(replace(dataset, bars=invalid), STUDY)

    def test_archive_to_reports_reproducibility_and_source_checks(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            transport, _ = two_month_transport()
            verified = build_dataset("BTCUSDT", "2024-12", "2025-01", root, transport=transport)
            scope = {**STUDY.registry["data"], "symbols": ["BTCUSDT"],
                     "first_month": "2024-12", "last_month": "2025-01"}
            fixture = replace(STUDY, registry={**STUDY.registry, "data": scope})
            with patch("alpha_lab.research.strategy_v08.load_study", return_value=fixture), patch.dict(
                    "alpha_lab.research.strategy_v08.DATASET_SHA256", {"BTCUSDT": verified["sha256"]}):
                self.assertEqual(run_study(root, root / "first", REGISTRY), "FAIL")
                self.assertEqual(run_study(root, root / "second", REGISTRY), "FAIL")
                one = (root / "first" / "BTCUSDT.json").read_bytes()
                self.assertEqual(one, (root / "second" / "BTCUSDT.json").read_bytes())
                report = json.loads(one)
                self.assertFalse(report["trading_enabled"])
                self.assertFalse(report["independently_sealed_holdout"])
                self.assertTrue(report["frozen_benchmark_parity_verified"])
                self.assertEqual(set(report["test_unsealed_descriptive_bootstrap"]), set(COMPARATORS))
                before = report["periods"]["test_unsealed"]["base_friction"]
                self.assertLess(before["candidate_after_primary_overhead_pct"], before["candidate"]["net_execution_return_pct"])
                self.assertEqual(before["flat"]["net_execution_return_pct"], 0)
                reference = runpy.run_path(str(REGISTRY.parents[1] / "scripts" / "audit_strategy_v08.py"))
                candles = load_csv(verified["csv"], quote_currency="USDT").bars
                prices = [(bar.time, float(bar.open), float(bar.close)) for bar in candles]
                self.assertEqual(reference["verify"](report, prices, fixture.registry), 32)
                with self.assertRaises(FileExistsError):
                    run_study(root, root / "first", REGISTRY)
                Path(verified["csv"]).write_text("changed", encoding="utf-8")
                with self.assertRaises(ValueError):
                    run_study(root, root / "tampered", REGISTRY)
                self.assertFalse((root / "tampered").exists())

    def test_registry_hash_fails_closed(self):
        with TemporaryDirectory() as temp:
            changed = Path(temp) / "registry.json"
            changed.write_bytes(REGISTRY.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "preregistered"):
                load_study(changed)


if __name__ == "__main__":
    unittest.main()
