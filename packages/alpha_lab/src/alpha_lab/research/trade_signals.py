"""Causal, versioned research signals shared by the live and historical paths."""
from dataclasses import dataclass
from decimal import Decimal

from alpha_lab.research.strategies.momentum import ema_series

STRATEGIES = ("ema-trend", "momentum", "channel-breakout", "mean-reversion", "regime-conditioned")
STRATEGY_VERSION = "1.0"
MIN_FEATURE_BARS = 52
HOLD_BARS = 6
STOP_ATR = Decimal("1.5")
TARGET_ATR = Decimal("3")
ENTRY_BAND_ATR = Decimal("0.5")


@dataclass(frozen=True)
class Regime:
    trend: str
    volatility: str
    reasons: tuple[str, ...]
    close: Decimal
    atr: Decimal
    atr_fraction: Decimal
    volatility_ratio: Decimal
    ema_fast: Decimal
    ema_slow: Decimal
    ema_slope: Decimal
    momentum: Decimal
    channel_high: Decimal
    channel_low: Decimal
    range_mean: Decimal


@dataclass(frozen=True)
class Signal:
    strategy: str
    direction: str
    reason: str
    invalidation: str
    stability: int = 0


def _mean(values):
    return sum(values) / len(values)


def classify_regime(bars):
    if len(bars) < MIN_FEATURE_BARS:
        raise ValueError("insufficient completed candles for regime features")
    closes = [bar.close for bar in bars]
    fast, slow = (ema_series(closes, length) for length in (12, 48))
    close = closes[-1]
    slope = fast[-1] / fast[-5] - 1
    momentum = close / closes[-13] - 1
    true_ranges = [max(b.high - b.low, abs(b.high - a.close), abs(b.low - a.close))
                   for a, b in zip(bars, bars[1:])]
    atr = _mean(true_ranges[-14:])
    prior_atr = _mean(true_ranges[-42:-14])
    ratio = atr / prior_atr if prior_atr else Decimal(0)
    volatility = ("HIGH" if ratio >= Decimal("1.6") else
                  "LOW" if Decimal(0) < ratio <= Decimal("0.65") else "NORMAL")
    gap = (fast[-1] - slow[-1]) / close
    threshold = max(Decimal("0.001"), atr / close / 2)
    if not atr or not prior_atr or true_ranges[-1] > atr * 4:
        trend, reason = "UNCERTAIN", "Insufficient range variation or abrupt range expansion"
    elif gap > threshold and slope > 0 and momentum > 0:
        trend, reason = "TRENDING_UP", "EMA 12 leads EMA 48 with rising slope and positive momentum"
    elif gap < -threshold and slope < 0 and momentum < 0:
        trend, reason = "TRENDING_DOWN", "EMA 12 trails EMA 48 with falling slope and negative momentum"
    elif abs(gap) <= threshold and abs(momentum) <= 2 * atr / close:
        trend, reason = "RANGE_BOUND", "EMA separation and momentum are small relative to ATR"
    else:
        trend, reason = "UNCERTAIN", "EMA separation, slope and momentum disagree"
    prior = bars[-21:-1]
    return Regime(trend, volatility, (reason, "ATR 14 compared with the preceding 28 true ranges"),
                  close, atr, atr / close, ratio, fast[-1], slow[-1], slope, momentum,
                  max(bar.high for bar in prior), min(bar.low for bar in prior), _mean(closes[-21:-1]))


def _directions(r):
    trend = {"TRENDING_UP": "LONG", "TRENDING_DOWN": "SHORT"}.get(r.trend, "FLAT")
    momentum = "LONG" if r.momentum > r.atr_fraction else "SHORT" if r.momentum < -r.atr_fraction else "FLAT"
    breakout = "LONG" if r.close > r.channel_high else "SHORT" if r.close < r.channel_low else "FLAT"
    mean_reversion = "FLAT"
    if r.trend == "RANGE_BOUND" and r.volatility != "HIGH":
        if r.close < r.range_mean - r.atr:
            mean_reversion = "LONG"
        elif r.close > r.range_mean + r.atr:
            mean_reversion = "SHORT"
    conditioned = trend if trend != "FLAT" and trend == momentum and r.volatility != "HIGH" else mean_reversion
    return trend, momentum, breakout, mean_reversion, conditioned


def generate_signals(bars, *, stability=True):
    regime = classify_regime(bars)
    directions = _directions(regime)
    previous = [_directions(classify_regime(bars[:-back])) for back in (1, 2)
                if stability and len(bars) - back >= MIN_FEATURE_BARS]
    descriptions = (
        ("EMA 12/48 separation confirmed by slope and momentum", "EMA trend confirmation disappears"),
        ("12-bar momentum exceeds one ATR relative to price", "Momentum falls below the ATR threshold"),
        ("Close breaks the prior 20-bar price channel", "A completed candle closes back inside the channel"),
        ("Close is at least one ATR from the 20-bar mean in a range", "Regime leaves the range or reaches the mean"),
        ("Trend plus momentum confirmation, or range reversion", "Regime and underlying signal stop agreeing"),
    )
    signals = []
    for i, (strategy, direction, description) in enumerate(zip(STRATEGIES, directions, descriptions)):
        count = 0 if direction == "FLAT" else 1
        for prior in previous:
            if not count or prior[i] != direction:
                break
            count += 1
        reason = description[0] if count else "Signal threshold is unmet"
        signals.append(Signal(strategy, direction, reason, description[1], count))
    return regime, tuple(signals)
