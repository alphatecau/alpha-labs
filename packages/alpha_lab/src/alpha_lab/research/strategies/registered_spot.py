"""Point-in-time OHLC breakout and range-reversion signals for v0.9."""
from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from statistics import mean

from alpha_lab.data.csv_import import Bar

HOUR = timedelta(hours=1)
MONDAY = datetime(1970, 1, 5, tzinfo=UTC)


@dataclass(frozen=True)
class Decision:
    enter: bool
    exit: bool
    stop_fraction: Decimal


def aggregate(bars, hours):
    """Return (last contributing hourly index, OHLCV) for complete UTC buckets."""
    if hours not in (4, 24, 168):
        raise ValueError("Expected four-hour, UTC daily or Monday-start weekly buckets")
    if not bars or any(bar.time.utcoffset() != timedelta(0) or bar.time.minute
                       or bar.time.second or bar.time.microsecond for bar in bars):
        raise ValueError("Expected UTC hourly opens")
    if any(now.time - prev.time != HOUR for prev, now in zip(bars, bars[1:])):
        raise ValueError("Cannot aggregate an incomplete hourly grid")
    first = -((bars[0].time - MONDAY) // HOUR) % hours
    for start in range(first, len(bars) - hours + 1, hours):
        window = bars[start:start + hours]
        yield start + hours - 1, Bar(
            window[0].time, window[0].open, max(bar.high for bar in window),
            min(bar.low for bar in window), window[-1].close, sum(bar.volume for bar in window),
        )


def timeframes(bars):
    return {hours: tuple(aggregate(bars, hours)) for hours in (4, 24, 168)}


def strategy_signals(frames, hourly_count, params, timing):
    """Decisions are events, not continuously forwarded targets."""
    family = params["family"]
    trend = family == "breakout"
    if not trend and family != "mean_reversion":
        raise ValueError(f"Unsupported strategy family: {family}")
    candles = frames[params["signal_hours"]]
    confirmations = frames[params["confirmation_hours"] if trend else 24]
    higher_indices = [idx for idx, _ in confirmations]
    higher_closes = [bar.close for _, bar in confirmations]
    needed = params["confirmation_bars"] if trend else params["range_days"] + 1
    lookback = params["entry_bars"] if trend else params["mean_bars"]
    atr_bars = timing["atr_bars"]
    floor, ceiling = Decimal(timing["stop_floor_fraction"]), Decimal(timing["stop_ceiling_fraction"])
    atr_multiple = Decimal(params["atr_multiple"])
    ranges = [Decimal(0)]  # The first true range lacks a prior close and is never used.
    signals = [None] * hourly_count
    for j in range(1, len(candles)):
        index, current = candles[j]
        prior_close = candles[j - 1][1].close
        ranges.append(max(current.high, prior_close) - min(current.low, prior_close))
        k = bisect_right(higher_indices, index)
        if j < max(atr_bars, lookback) or k < needed:
            continue
        atr = mean(ranges[j - atr_bars + 1:j + 1])
        if atr <= 0:
            continue
        if trend:
            entry = current.close > max(bar.high for _, bar in candles[j - lookback:j])
            entry &= higher_closes[k - 1] > mean(higher_closes[k - needed:k])
            exit_ = current.close < min(bar.low for _, bar in candles[j - params["exit_bars"]:j])
        else:
            centre = mean(bar.close for _, bar in candles[j - lookback:j])
            range_return = abs(higher_closes[k - 1] / higher_closes[k - needed] - 1)
            ranging = range_return <= Decimal(params["max_range_return_fraction"])
            entry = ranging and centre - current.close >= Decimal(params["entry_atr"]) * atr
            exit_ = not ranging or current.close >= centre
        distance = min(ceiling, max(floor, atr * atr_multiple / current.close))
        signals[index] = Decision(entry, exit_, distance)
    return tuple(signals)
