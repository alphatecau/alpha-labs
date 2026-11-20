"""Preregistered R1: deterministic, close-only regime filter; research-only."""
from decimal import Decimal
from alpha_lab.research.strategies.momentum import ema_signal

def r1_signal(closes):
    """R1 signal at bar t; engine executes at open t+1. No fitting or holdout access."""
    from decimal import localcontext
    if any(not c.is_finite() or c <= 0 for c in closes):
        raise ValueError("finite positive closes required")
    baseline = ema_signal(closes, 12, 48)
    result = [False] * len(closes)
    with localcontext() as ctx:
        ctx.prec = 34
        returns = [None] + [(closes[i] / closes[i-1]).ln() for i in range(1, len(closes))]
        vol = [None] * len(closes)
        for t in range(48, len(closes)):
            window = returns[t-47:t+1]
            mean = sum(window) / Decimal(48)
            vol[t] = (sum((x - mean)**2 for x in window) / Decimal(48)).sqrt()
        # Current observation is excluded from the percentile distribution.
        for t in range(768, len(closes)):
            historical = sorted(vol[t-720:t])
            threshold = historical[539]  # nearest-rank 75th percentile: ceil(.75*720)-1
            sma = sum(closes[t-199:t+1]) / Decimal(200)
            result[t] = bool(baseline[t] and closes[t] > sma and vol[t] <= threshold)
    return result
