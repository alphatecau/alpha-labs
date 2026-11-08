"""Pre-registered causal hourly market-regime labels; no trading signals.

Each label at hour i uses closes only through i-1. Regime attribution requires
the verified underlying OHLC dataset, not the archived NAV-only report.
"""
from __future__ import annotations
from math import log, sqrt, isfinite

def causal_regime_labels(closes: list[float], *, slow_hours: int = 168,
                         fast_hours: int = 48) -> list[str]:
    if not (24 <= fast_hours < slow_hours) or len(closes) < slow_hours+1:
        raise ValueError("Insufficient history or invalid frozen regime windows")
    if any(not isfinite(x) or x <= 0 for x in closes):
        raise ValueError("Invalid prices")
    labels = ["INSUFFICIENT_HISTORY"] * len(closes)
    squared = [0.0] + [log(closes[j]/closes[j-1])**2 for j in range(1,len(closes))]
    prefix = [0.0]
    for value in squared:
        prefix.append(prefix[-1]+value)
    for i in range(slow_hours+1,len(closes)):
        long_ret = log(closes[i-1]/closes[i-1-slow_hours])
        # Hour i uses returns through hour i-1 only.
        fast_sum = prefix[i]-prefix[i-fast_hours]
        slow_sum = prefix[i-fast_hours]-prefix[i-slow_hours]
        fast_vol = sqrt(max(0.0,fast_sum/fast_hours))
        slow_vol = sqrt(max(0.0,slow_sum/(slow_hours-fast_hours)))
        if slow_vol > 0 and fast_vol > 1.5*slow_vol:
            labels[i] = "VOLATILITY_EXPANSION"
        elif long_ret > .05:
            labels[i] = "UPTREND"
        elif long_ret < -.05:
            labels[i] = "DOWNTREND"
        else:
            labels[i] = "SIDEWAYS"
    return labels
