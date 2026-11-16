"""Offline, fail-closed Coinbase research candle import. Never connects to an exchange.

Only an operator-reviewed, account-free snapshot is accepted. This module has no
paper-order, journal, network, authentication or execution dependencies.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

PRODUCTS = frozenset(("BTC-USD", "ETH-USD", "SOL-USD"))
INTERVALS = {"4h": timedelta(hours=4), "1d": timedelta(days=1)}
TOP_FIELDS = frozenset(("schema_version", "provider", "product_id", "product_type",
                        "quote_currency", "granularity", "collected_at", "candles"))
CANDLE_FIELDS = frozenset(("start", "open", "high", "low", "close", "volume", "complete"))
MAX_BYTES = 2_000_000
MAX_CANDLES = 350


def _utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be RFC3339 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp") from exc
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("non-UTC timestamp")
    return parsed


def _number(value, *, positive=False):
    if not isinstance(value, str) or not value or len(value) > 48:
        raise ValueError("numeric values must be bounded decimal strings")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal") from exc
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise ValueError("non-finite, negative or zero price")
    return number


def validate_snapshot(snapshot, *, now=None, min_candles=48):
    """Return immutable-to-caller validated research values; raise on any ambiguity.

    Candles must be complete, contiguous, strictly ordered and closed by collection.
    A fresh collection time alone cannot make stale market history current.
    """
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() != timedelta(0):
        raise ValueError("UTC verification clock required")
    if not isinstance(snapshot, dict) or frozenset(snapshot) != TOP_FIELDS:
        raise ValueError("snapshot schema mismatch or unexpected account data")
    if (type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != 1
            or snapshot["provider"] != "AlphaLabs Coinbase read-only"
            or snapshot["product_id"] not in PRODUCTS
            or snapshot["product_type"] != "SPOT"
            or snapshot["quote_currency"] != "USD"
            or snapshot["granularity"] not in INTERVALS):
        raise ValueError("unsupported research source or instrument")
    collected = _utc(snapshot["collected_at"])
    if not timedelta(0) <= now - collected <= timedelta(minutes=15):
        raise ValueError("collection timestamp stale or future")
    interval = INTERVALS[snapshot["granularity"]]
    rows = snapshot["candles"]
    if not isinstance(rows, list) or not min_candles <= len(rows) <= MAX_CANDLES:
        raise ValueError("insufficient or excessive candle history")
    clean = []
    previous = None
    for row in rows:
        if not isinstance(row, dict) or frozenset(row) != CANDLE_FIELDS or row["complete"] is not True:
            raise ValueError("invalid or incomplete candle")
        start = _utc(row["start"])
        if start.timestamp() % interval.total_seconds() != 0:
            raise ValueError("misaligned candle")
        if previous is not None and start - previous != interval:
            raise ValueError("duplicate, out-of-order or missing candle")
        if start + interval > collected:
            raise ValueError("unclosed candle")
        values = {field: _number(row[field], positive=field != "volume")
                  for field in ("open", "high", "low", "close", "volume")}
        if values["high"] < values["low"] or any(
                not values["low"] <= values[field] <= values["high"]
                for field in ("open", "close")):
            raise ValueError("inconsistent OHLC")
        clean.append({"start": start.isoformat(), **{k: str(v) for k, v in values.items()}})
        previous = start
    if collected - (previous + interval) > interval:
        raise ValueError("last closed candle is stale")
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return {"status": "VERIFIED_RESEARCH_ONLY", "product_id": snapshot["product_id"],
            "granularity": snapshot["granularity"], "collected_at": collected.isoformat(),
            "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "candles": tuple(clean), "simulated_only": True,
            "live_execution_authorised": False}


def load_snapshot(path, *, now=None, min_candles=48):
    """Read an explicitly supplied local file; never fetch remote URLs."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("missing, linked or oversized snapshot")
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("oversized snapshot")
    try:
        snapshot = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid snapshot JSON") from exc
    return validate_snapshot(snapshot, now=now, min_candles=min_candles)
