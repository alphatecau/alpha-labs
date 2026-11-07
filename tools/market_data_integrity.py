"""Fail-closed point-in-time market event and quote validation.

Independent offline primitives for future adapters. These checks do not certify
vendor licensing, actual fills, corporate actions or data completeness.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


class MarketDataError(ValueError):
    pass


def utc_millis(value: str) -> int:
    if type(value) is not str or not value.endswith("Z"):
        raise MarketDataError("timestamp must be an explicit UTC ISO-8601 Z string")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MarketDataError("invalid timestamp") from exc
    if parsed.utcoffset().total_seconds() != 0:
        raise MarketDataError("non-UTC timestamp")
    return int(parsed.timestamp() * 1000)


def positive_decimal(value, label: str) -> Decimal:
    if type(value) not in (str, int, float, Decimal):
        raise MarketDataError(f"{label} must be numeric")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise MarketDataError(f"{label} is invalid") from exc
    if not number.is_finite() or number <= 0:
        raise MarketDataError(f"{label} must be finite and positive")
    return number


def validate_quote(quote: dict, *, max_staleness_ms: int = 5000) -> dict:
    """Reject crossed, stale, future, reordered or invalid quote observations."""
    if type(quote) is not dict:
        raise MarketDataError("quote must be an object")
    for key in ("venue", "instrument", "source_id"):
        if type(quote.get(key)) is not str or not quote[key].strip():
            raise MarketDataError(f"missing {key}")
    if type(max_staleness_ms) is not int or max_staleness_ms < 0:
        raise MarketDataError("invalid staleness limit")
    event = utc_millis(quote.get("event_time"))
    received = utc_millis(quote.get("received_time"))
    decision = utc_millis(quote.get("decision_time"))
    if event > received or received > decision:
        raise MarketDataError("future or noncausal timestamps")
    if decision - received > max_staleness_ms:
        raise MarketDataError("stale quote")
    bid = positive_decimal(quote.get("bid"), "bid")
    ask = positive_decimal(quote.get("ask"), "ask")
    bid_size = positive_decimal(quote.get("bid_size"), "bid_size")
    ask_size = positive_decimal(quote.get("ask_size"), "ask_size")
    if bid > ask:
        raise MarketDataError("crossed market")
    return {
        "venue": quote["venue"], "instrument": quote["instrument"],
        "source_id": quote["source_id"], "event_ms": event,
        "received_ms": received, "decision_ms": decision,
        "bid": str(bid), "ask": str(ask),
        "bid_size": str(bid_size), "ask_size": str(ask_size),
        "spread_bps": str((ask - bid) / ((ask + bid) / 2) * 10000),
    }


def conservative_fill_cost_bps(quote: dict, *, side: str, quantity,
                               fee_bps, impact_bps=0) -> Decimal:
    """Full spread vs midpoint + assumed fee and impact, for a single fill.

    This is a quote-based scenario, not executable order-book calibration.
    Quantity must fit top-of-book size; larger orders are rejected.
    """
    if side not in ("BUY", "SELL"):
        raise MarketDataError("unsupported side")
    bid, ask = Decimal(quote["bid"]), Decimal(quote["ask"])
    qty = positive_decimal(quantity, "quantity")
    depth = Decimal(quote["ask_size"] if side == "BUY" else quote["bid_size"])
    if qty > depth:
        raise MarketDataError("insufficient top-of-book quantity")
    fee = Decimal(str(fee_bps))
    impact = Decimal(str(impact_bps))
    if not fee.is_finite() or not impact.is_finite() or fee < 0 or impact < 0:
        raise MarketDataError("invalid cost assumptions")
    midpoint = (bid + ask) / 2
    half_spread = ((ask - bid) / 2) / midpoint * 10000
    return half_spread + fee + impact
