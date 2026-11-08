"""Preregistered four-hour breakout signals for offline, long/flat research.

No orders, API access, profitability claims or live trading. Each signal at
hour i uses only the most recently completed 4h candle at or before i.
The existing replay engine consumes signals[i-1] at hour i's open.
"""
from __future__ import annotations
from decimal import Decimal
from alpha_lab.data.csv_import import Bar

def breakout_signals(bars: tuple[Bar, ...], *, breakout_lookback: int = 20,
                     ema_period: int = 200, slope_period: int = 10,
                     atr_period: int = 14, max_hold_bars: int = 30,
                     trailing_atr: Decimal = Decimal("3"),
                     min_atr_fraction: Decimal = Decimal("0.005"),
                     max_atr_fraction: Decimal = Decimal("0.06")) -> list[bool]:
    if (breakout_lookback != 20 or ema_period != 200 or slope_period != 10
        or atr_period != 14 or max_hold_bars != 30
        or trailing_atr != Decimal("3")
        or min_atr_fraction != Decimal("0.005")
        or max_atr_fraction != Decimal("0.06")):
        raise ValueError("Frozen research parameters cannot be optimised in this protocol")
    if not bars:
        return []
    # Bars are expected to be validated by Dataset before this function.
    for i, bar in enumerate(bars):
        if bar.time.tzinfo is None or bar.time.utcoffset().total_seconds() != 0:
            raise ValueError("UTC timestamps required")
        if bar.time.minute or bar.time.second or bar.time.microsecond:
            raise ValueError("Full-hour candles required")
        if i and (bar.time - bars[i-1].time).total_seconds() != 3600:
            raise ValueError("Missing, duplicated or unordered hourly candle")
        if bar.close <= 0 or bar.high < bar.low:
            raise ValueError("Invalid price")
    # Do not treat incomplete leading or trailing four-hour groups as candles.
    buckets = {}
    for index, bar in enumerate(bars):
        key = (bar.time.year, bar.time.month, bar.time.day, bar.time.hour // 4)
        buckets.setdefault(key, []).append((index, bar))
    candles = []
    for bucket in buckets.values():
        if len(bucket) != 4 or bucket[0][1].time.hour % 4 != 0:
            continue
        first, last = bucket[0], bucket[-1]
        candles.append((last[0], first[1].open,
                        max(x.high for _, x in bucket),
                        min(x.low for _, x in bucket), last[1].close))
    output = [False] * len(bars)
    if not candles:
        return output
    alpha = Decimal(2) / Decimal(ema_period + 1)
    ema = []
    tr = []
    for j, (_, opening, high, low, close) in enumerate(candles):
        ema.append(close if j == 0 else alpha * close + (1-alpha) * ema[-1])
        prev_close = candles[j-1][4] if j else close
        tr.append(max(high-low, abs(high-prev_close), abs(low-prev_close)))
    holding = False
    held_bars = 0
    highest_close = Decimal(0)
    for j, (last_hour, opening, high, low, close) in enumerate(candles):
        if j < max(ema_period+slope_period, breakout_lookback, atr_period):
            continue
        atr = sum(tr[j-atr_period+1:j+1]) / Decimal(atr_period)
        ratio = atr / close
        if holding:
            held_bars += 1
            highest_close = max(highest_close, close)
            if (close < highest_close - trailing_atr*atr
                or held_bars >= max_hold_bars or close < ema[j]):
                holding = False
        else:
            prior_high = max(x[2] for x in candles[j-breakout_lookback:j])
            if (close > prior_high and close > ema[j] and ema[j] > ema[j-slope_period]
                and min_atr_fraction <= ratio <= max_atr_fraction):
                holding = True
                held_bars = 0
                highest_close = close
        # Carry completed four-hour close signal through following hourly bars.
        for index in range(last_hour, min(last_hour+4, len(bars))):
            output[index] = holding
    return output
