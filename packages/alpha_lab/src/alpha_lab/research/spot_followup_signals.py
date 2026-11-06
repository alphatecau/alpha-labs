"""Exploratory v0.9 signals on development and validation history only."""
from bisect import bisect_right
from dataclasses import dataclass
from decimal import Decimal
from statistics import mean

from alpha_lab.research.strategies.regime_trend import Regime
from alpha_lab.research.strategies.registered_spot import Decision, aggregate

SIGNAL_HOURS = 4
DAILY_LOOKBACK = 30
EXPANSION_MULTIPLE = Decimal("1.5")


@dataclass(frozen=True)
class TrendObservation:
    regime: Regime
    momentum: Decimal
    long: Decision
    short_signal: bool


def trend_observations(bars, regimes, parameters, stop):
    """Use only complete 4h and daily candles and the existing hourly classifier."""
    daily = tuple(aggregate(bars, 24))
    daily_indices = [index for index, _ in daily]
    daily_closes = [bar.close for _, bar in daily]
    out = [None] * len(bars)
    for index, _ in aggregate(bars, SIGNAL_HOURS):
        known = bisect_right(daily_indices, index)
        current = regimes[index]
        if known < DAILY_LOOKBACK or index < parameters.volatility_hours or current.momentum is None:
            continue
        prior = regimes[index - parameters.volatility_hours].hourly_volatility
        regime = current.regime
        if prior and current.hourly_volatility >= prior * EXPANSION_MULTIPLE:
            regime = Regime.HIGH_VOL
        context = daily_closes[known - DAILY_LOOKBACK:known]
        daily_close, centre = context[-1], mean(context)
        momentum = current.momentum
        threshold = parameters.entry_momentum_fraction
        enter = regime is Regime.UP and momentum >= threshold and daily_close > centre
        exit_ = regime is Regime.DOWN or momentum <= 0
        short = regime is Regime.DOWN and momentum <= -threshold and daily_close < centre
        out[index] = TrendObservation(regime, momentum, Decision(enter, exit_, stop), short)
    return tuple(out)


def rotation_signals(observations):
    """At each decision keep the strongest eligible long or hold cash."""
    streams = {symbol: [] for symbol in observations}
    for points in zip(*observations.values(), strict=True):
        ranked = [(symbol, point) for symbol, point in zip(streams, points, strict=True)
                  if point is not None and point.long.enter]
        leader = max(ranked, key=lambda item: item[1].momentum, default=(None, None))[0]
        for symbol, point in zip(streams, points, strict=True):
            streams[symbol].append(None if point is None else Decision(
                symbol == leader, symbol != leader, point.long.stop_fraction,
            ))
    return {symbol: tuple(stream) for symbol, stream in streams.items()}
