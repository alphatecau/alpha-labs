"""Offline research-only signal report from validated Coinbase candle snapshots.

No exchange access, account access, order submission or paper-runtime mutation.
"""
from decimal import Decimal

from alpha_lab.research.coinbase_research_import import validate_snapshot


def _ema(values, span):
    factor = Decimal(2) / Decimal(span + 1)
    current = values[0]
    for value in values[1:]:
        current += factor * (value - current)
    return current


def research_report(snapshot, *, now=None):
    """Return descriptive EMA trend only; never an executable trade signal."""
    validated = validate_snapshot(snapshot, now=now, min_candles=60)
    candles = validated["candles"]
    closes = [Decimal(row["close"]) for row in candles]
    fast = _ema(closes, 12)
    slow = _ema(closes, 48)
    last = closes[-1]
    if fast > slow and last > fast:
        trend = "UPTREND_OBSERVED"
    elif fast < slow and last < fast:
        trend = "DOWNTREND_OBSERVED"
    else:
        trend = "MIXED"
    return {
        "status": "RESEARCH_ONLY_NOT_VALIDATED_ALPHA",
        "product_id": validated["product_id"],
        "granularity": validated["granularity"],
        "source_sha256": validated["sha256"],
        "candle_count": len(candles),
        "close_usd": str(last),
        "ema12_usd": str(fast),
        "ema48_usd": str(slow),
        "trend_observation": trend,
        "decision": "FLAT",
        "risk_override": "HALT",
        "paper_execution_authorised": False,
        "live_execution_authorised": False,
        "limitations": (
            "Descriptive EMA values are not a validated trading edge",
            "EMA warmup starts at the first available closed candle",
            "No executable order-book, costs, liquidity or independent risk approval",
        ),
    }
