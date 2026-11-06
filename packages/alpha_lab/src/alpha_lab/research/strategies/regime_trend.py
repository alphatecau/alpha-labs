"""Point-in-time regime-filtered momentum signals for spot research."""
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Sequence

from alpha_lab.research.strategies.momentum import ema_series


class Regime(StrEnum):
    UP = "TRENDING_UP"
    DOWN = "TRENDING_DOWN"
    RANGE = "RANGING"
    HIGH_VOL = "HIGH_VOLATILITY"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class MomentumParameters:
    fast_hours: int
    slow_hours: int
    slope_hours: int
    momentum_hours: int
    volatility_hours: int
    min_trend_spread_fraction: Decimal
    entry_momentum_fraction: Decimal
    max_hourly_volatility_fraction: Decimal

    def __post_init__(self):
        hours = (self.fast_hours, self.slow_hours, self.slope_hours,
                 self.momentum_hours, self.volatility_hours)
        if any(type(h) is not int or not 2 <= h <= 720 for h in hours):
            raise ValueError("Indicator horizons must be 2–720 hours")
        if self.fast_hours >= self.slow_hours:
            raise ValueError("Fast EMA must be shorter than slow EMA")
        thresholds = (self.min_trend_spread_fraction, self.entry_momentum_fraction,
                      self.max_hourly_volatility_fraction)
        if any(not isinstance(t, Decimal) or not t.is_finite()
               or not 0 < t <= Decimal("0.10") for t in thresholds):
            raise ValueError("Indicator thresholds must be finite fractions in (0, 0.10]")

    @property
    def warmup_hours(self) -> int:
        return max(self.slow_hours + self.slope_hours,
                   self.momentum_hours, self.volatility_hours)


@dataclass(frozen=True)
class Signal:
    regime: Regime
    momentum: Decimal | None
    hourly_volatility: Decimal | None
    target_long: bool


def classify(spread: Decimal, slope: Decimal, volatility: Decimal,
             params: MomentumParameters) -> Regime:
    if volatility >= params.max_hourly_volatility_fraction:
        return Regime.HIGH_VOL
    if abs(spread) < params.min_trend_spread_fraction:
        return Regime.RANGE
    if spread > 0 and slope > 0:
        return Regime.UP
    if spread < 0 and slope < 0:
        return Regime.DOWN
    return Regime.UNCERTAIN


def momentum_signals(closes: Sequence[Decimal], params: MomentumParameters) -> tuple[Signal, ...]:
    """Each target uses at most the close at its own index. FLAT is the default."""
    if not closes or any(not isinstance(close, Decimal) or not close.is_finite()
                         or close <= 0 for close in closes):
        raise ValueError("Complete, finite, positive closes required")
    prices = list(closes)
    fast = ema_series(prices, params.fast_hours)
    slow = ema_series(prices, params.slow_hours)
    warmup = params.warmup_hours
    n = params.volatility_hours
    hourly_returns = [Decimal(0)]  # No return exists for the first close.
    total = squares = Decimal(0)
    signals = [Signal(Regime.UNCERTAIN, None, None, False)]
    for i in range(1, len(prices)):
        latest = prices[i] / prices[i - 1] - 1
        hourly_returns.append(latest)
        expired = hourly_returns[i - n] if i >= n else Decimal(0)
        total += latest - expired
        squares += latest * latest - expired * expired
        if i < warmup:
            signals.append(Signal(Regime.UNCERTAIN, None, None, False))
            continue
        # A tiny negative variance from Decimal cancellation represents zero.
        variance = (squares - total * total / n) / (n - 1)
        volatility = max(variance, Decimal(0)).sqrt()
        spread = fast[i] / slow[i] - 1
        slope = slow[i] / slow[i - params.slope_hours] - 1
        momentum = prices[i] / prices[i - params.momentum_hours] - 1
        regime = classify(spread, slope, volatility, params)
        signals.append(Signal(
            regime, momentum, volatility,
            regime is Regime.UP and momentum >= params.entry_momentum_fraction,
        ))
    return tuple(signals)
