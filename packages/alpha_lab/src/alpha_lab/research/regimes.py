"""Research-only, causal market regime classifier. No orders or execution."""
from dataclasses import dataclass
from math import isfinite
from statistics import pstdev

@dataclass(frozen=True)
class RegimeAssessment:
    regime: str
    trend_return: float
    realised_volatility: float
    observations: int
    eligible: bool

def classify_regime(closes, *, lookback=20, trend_threshold=0.03,
                    volatility_threshold=0.025, crash_threshold=-0.10):
    """Classify a trailing window only; returns UNKNOWN on inadequate data.

    Thresholds are research assumptions, not calibrated trading parameters.
    Volatility is the population standard deviation of simple per-bar returns.
    """
    if lookback < 3 or any(not isfinite(float(x)) or float(x) <= 0 for x in closes):
        raise ValueError("positive finite prices and lookback >= 3 required")
    if len(closes) < lookback + 1:
        return RegimeAssessment("UNKNOWN", 0.0, 0.0, len(closes), False)
    window = tuple(float(x) for x in closes[-(lookback + 1):])
    returns = [b / a - 1.0 for a, b in zip(window, window[1:])]
    trend = window[-1] / window[0] - 1.0
    vol = pstdev(returns)
    if trend <= crash_threshold:
        regime = "CRASH"
    elif vol >= volatility_threshold:
        regime = "JUMPY"
    elif abs(trend) >= trend_threshold:
        regime = "CALM_TREND"
    else:
        regime = "SIDEWAYS"
    return RegimeAssessment(regime, trend, vol, len(window), regime == "CALM_TREND")
