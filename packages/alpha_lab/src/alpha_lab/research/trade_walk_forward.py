"""Purged, embargoed development replay of the exact versioned 4h rules."""
from dataclasses import asdict, dataclass
from datetime import timedelta
from decimal import Decimal
from statistics import mean
from math import prod

from alpha_lab.data.adapters.coinbase_candles import (
    BARS_REQUIRED, aggregate_bars, check_cadence, check_research_window,
)
from alpha_lab.research.trade_intelligence import Evidence, OFFLINE
from alpha_lab.research.trade_risk import MIN_REWARD_TO_RISK
from alpha_lab.research.trade_signals import (
    ENTRY_BAND_ATR, HOLD_BARS, STOP_ATR, STRATEGIES, STRATEGY_VERSION, TARGET_ATR, generate_signals,
)
from alpha_lab.strategy_evidence import ValidationConfig, evaluate_oos

HOURS_PER_BAR = 4
FOLD_BARS = 42
HOUR = timedelta(hours=1)
BASE_SIDE_BPS = Decimal("20")
STRESS_SIDE_BPS = Decimal("40")
MULTIPLE_TESTS = 3 * len(STRATEGIES) * 2 * (1 + 3 * 3)
BENCHMARK = "same-window buy-and-hold, 20 bps per side"
DIRECTIONS = ("LONG", "SHORT")


@dataclass(frozen=True)
class ModelledTrade:
    entry_index: int
    marks: tuple[Decimal, ...]
    entry: Decimal
    direction: int
    trend: str
    volatility: str

    def liquidation_path(self, side_bps):
        friction = side_bps / 10000
        return tuple(_liquidation_equity(self.entry, mark, self.direction, friction)
                     for mark in self.marks)


def _liquidation_equity(entry, mark, direction, friction):
    return 1 + direction * (mark / entry - 1) - friction * (1 + mark / entry)


def _trade(hourly, entry_index, regime, direction):
    entry = hourly[entry_index].open
    if abs(entry - regime.close) > ENTRY_BAND_ATR * regime.atr:
        return None
    sign = 1 if direction == "LONG" else -1
    stop, target = entry - sign * STOP_ATR * regime.atr, entry + sign * TARGET_ATR * regime.atr
    if not 0 < min(stop, target) < entry < max(stop, target):
        return None
    friction = BASE_SIDE_BPS / 10000
    reward = _liquidation_equity(entry, target, sign, friction) - 1
    loss = 1 - _liquidation_equity(entry, stop, sign, friction)
    if reward < MIN_REWARD_TO_RISK * loss:
        return None
    marks = []
    for bar in hourly[entry_index:entry_index + HOLD_BARS * HOURS_PER_BAR]:
        adverse = bar.low if sign == 1 else bar.high
        favourable = bar.high if sign == 1 else bar.low
        if sign * (adverse - stop) <= 0:
            # Both levels in the same bar resolve to the adverse exit.
            marks.append(min(bar.open, stop) if sign == 1 else max(bar.open, stop))
            break
        if sign * (favourable - target) >= 0:
            marks.append(target)
            break
        marks.append(bar.close)
    return ModelledTrade(entry_index, tuple(marks), entry, sign, regime.trend, regime.volatility)


def _fold_path(trades, start_hour, end_hour, side_bps):
    # Each mark is liquidation equity including modeled costs, including while open.
    returns = [0.0] * (end_hour - start_hour)
    for trade in trades:
        last = Decimal(1)
        for offset, equity in enumerate(trade.liquidation_path(side_bps)):
            if equity <= 0:
                raise ValueError("modelled return violates positive equity")
            returns[trade.entry_index + offset - start_hour] = float(equity / last - 1)
            last = equity
    return returns


def _metrics(fold_trades, windows, hourly, direction, regime=None):
    fold_means, stressed, folds, passive, trade_returns = [], [], [], [], []
    peak = equity = 1.0
    drawdown = 0.0
    for (start, end), trades in zip(windows, fold_trades):
        if regime is not None:
            trades = [t for t in trades if (t.trend, t.volatility) == regime]
        base_path = _fold_path(trades, start, end, BASE_SIDE_BPS)
        stress_path = _fold_path(trades, start, end, STRESS_SIDE_BPS)
        fold_means.append(mean(prod(1 + r for r in base_path[i:i + HOURS_PER_BAR]) - 1
                               for i in range(0, len(base_path), HOURS_PER_BAR)))
        stressed.extend(prod(1 + r for r in stress_path[i:i + HOURS_PER_BAR]) - 1
                        for i in range(0, len(stress_path), HOURS_PER_BAR))
        folds.append(prod(1 + r for r in base_path) - 1)
        fee = BASE_SIDE_BPS / 10000
        benchmark = float(hourly[end - 1].close * (1 - fee) / (hourly[start].open * (1 + fee)) - 1)
        passive.append(benchmark)
        trade_returns.extend(float(t.liquidation_path(BASE_SIDE_BPS)[-1] - 1) for t in trades)
        for change in base_path:
            equity *= 1 + change
            peak = max(peak, equity)
            drawdown = max(drawdown, 1 - equity / peak)

    lower, uncertainty = None, "INSUFFICIENT_TRADES_OR_FOLDS"
    if len(trade_returns) >= 2 and len(folds) >= 3:
        # Each embargo-separated fold is a unit. No bootstrap block spans a gap.
        screen = evaluate_oos(tuple(fold_means), trades=len(trade_returns), fold_net_returns=tuple(folds),
                              additional_cost_per_period=0,
                              config=ValidationConfig(min_observations=6, block_size=1,
                                                      confidence=1 - 0.05 / MULTIPLE_TESTS,
                                                      bootstrap_draws=MULTIPLE_TESTS * 40))
        lower = screen.lower_confidence_bound
        uncertainty = screen.status
    return {
        "direction": direction, "trades": len(trade_returns), "folds": len(folds),
        "positive_folds": sum(value > 0 for value in folds),
        "net_modelled_return": equity - 1,
        "stressed_modelled_return": prod(1 + r for r in stressed) - 1,
        "passive_modelled_return": prod(1 + r for r in passive) - 1,
        "mean_net_trade_return": mean(trade_returns) if trade_returns else None,
        "adjusted_lower_per_bar": lower, "uncertainty_status": uncertainty,
        "stressed_mean_per_bar": mean(stressed), "max_drawdown": drawdown,
        "benchmark_excess_per_bar": mean(folds[i] - passive[i] for i in range(len(folds))) / FOLD_BARS,
        "fold_returns": folds,
    }


def walk_forward(product, hourly, *, source, capture_sha256):
    """Replay fixed rules. Entry uses the next hourly open after publication delay."""
    if len(hourly) < (BARS_REQUIRED + FOLD_BARS) * HOURS_PER_BAR or len(hourly) % HOURS_PER_BAR:
        raise ValueError("insufficient or misaligned 4h replay history")
    window_start, window_end = hourly[0].time, hourly[-1].time + HOUR
    check_research_window(window_start, window_end)
    if window_start.hour % HOURS_PER_BAR or window_start.minute or window_start.second or window_start.microsecond:
        raise ValueError("UTC-aligned 4h replay required")
    check_cadence(hourly, 3600)
    four_hour = aggregate_bars(hourly, HOURS_PER_BAR)
    pairs = [(strategy, direction) for strategy in STRATEGIES for direction in DIRECTIONS]
    results = {key: [] for key in pairs}
    windows = []
    for start in range(BARS_REQUIRED, len(four_hour) - FOLD_BARS + 1, FOLD_BARS + HOLD_BARS):
        end = start + FOLD_BARS
        windows.append((start * HOURS_PER_BAR, end * HOURS_PER_BAR))
        trades = {key: [] for key in pairs}
        until = dict.fromkeys(pairs, 0)
        # Purge labels/trades that could extend beyond this fold.
        for index in range(start, end - HOLD_BARS):
            regime, signals = generate_signals(four_hour[index - BARS_REQUIRED:index], stability=False)
            if regime.trend == "UNCERTAIN":
                continue
            entry = index * HOURS_PER_BAR + 1
            for signal in signals:
                key = (signal.strategy, signal.direction)
                if key not in trades or entry < until[key]:
                    continue
                trade = _trade(hourly, entry, regime, signal.direction)
                if trade:
                    trades[key].append(trade)
                    until[key] = entry + len(trade.marks)
        for key in pairs:
            results[key].append(trades[key])

    comparisons = []
    for (strategy, direction), trades in results.items():
        summary = _metrics(trades, windows, hourly, direction)
        regimes = sorted({(t.trend, t.volatility) for fold in trades for t in fold})
        diagnostics = []
        for trend, volatility in regimes:
            scoped = _metrics(trades, windows, hourly, direction, (trend, volatility))
            evidence = Evidence(product, "4h", strategy, STRATEGY_VERSION, direction, trend, volatility,
                                window_start, window_end, BENCHMARK, source, 2 * BASE_SIDE_BPS,
                                scoped["trades"], scoped["folds"], scoped["positive_folds"],
                                scoped["mean_net_trade_return"], scoped["adjusted_lower_per_bar"],
                                scoped["stressed_mean_per_bar"], scoped["max_drawdown"],
                                scoped["benchmark_excess_per_bar"])
            item = asdict(evidence)
            item.update(window_start=window_start.isoformat(), window_end=window_end.isoformat(),
                        round_trip_bps=str(2 * BASE_SIDE_BPS), uncertainty_status=scoped["uncertainty_status"])
            diagnostics.append(item)
        comparisons.append({"strategy": strategy, **summary, "by_regime": diagnostics})
    return {
        "product": product, "source": source, "mode": OFFLINE, "timeframe": "4h",
        "history_start_utc": window_start.isoformat(), "history_end_utc": window_end.isoformat(),
        "capture_sha256": capture_sha256,
        "strategy_version": STRATEGY_VERSION, "observed_hourly_bars": len(hourly),
        "fold_windows": [[hourly[a].time.isoformat(), (hourly[b - 1].time + HOUR).isoformat()]
                         for a, b in windows],
        "comparisons": comparisons, "bootstrap_multiple_testing_comparisons": MULTIPLE_TESTS,
        "benchmark": BENCHMARK, "round_trip_bps": [str(2 * BASE_SIDE_BPS), str(2 * STRESS_SIDE_BPS)],
        "status": "UNVERIFIED_DEVELOPMENT_REPLAY", "promotion_authorised": False,
        "limitations": [
            "Fixed rules and previously unsealed data. No independent holdout or executable fills.",
            "Folds score 42 four-hour bars with six-bar embargoes and fold-boundary trade purging.",
            "Hourly open after signal availability; ambiguous stop/target bars resolve adversely.",
            "Costs assume 10 bps fees, 5 bps slippage and 5 bps half-spread per side; doubled stress.",
            "Hourly mark-to-market path, one position per strategy/direction and independent comparisons.",
            "Short comparisons are directional research without modeled borrowing or funding.",
            "Fold-level bootstrap uses Bonferroni correction across the full comparison family.",
            "At least 40 trades and independent promotion are required for research approval.",
        ],
    }
