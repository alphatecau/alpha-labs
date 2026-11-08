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
    for i in range(slow_hours+1,len(closes)):
        prior = closes[:i]
        long_ret = log(prior[-1]/prior[-1-slow_hours])
        returns = [log(prior[j]/prior[j-1]) for j in range(i-slow_hours,i)]
        fast = returns[-fast_hours:]
        slow = returns[:-fast_hours]
        fast_vol = sqrt(sum(x*x for x in fast)/len(fast))
        slow_vol = sqrt(sum(x*x for x in slow)/len(slow))
        if slow_vol > 0 and fast_vol > 1.5*slow_vol:
            labels[i] = "VOLATILITY_EXPANSION"
        elif long_ret > .05:
            labels[i] = "UPTREND"
        elif long_ret < -.05:
            labels[i] = "DOWNTREND"
        else:
            labels[i] = "SIDEWAYS"
    return labels
