"""Offline daily equity/ETF research CSV importer with explicit session calendar.

No exchange calendar or price authenticity is inferred. No network or trading.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path

from alpha_lab.data.provider_neutral import CanonicalOHLCV, ResearchDataset
from alpha_lab.data.session_pit import SessionCalendar, PointInTimeRecord, validate_daily_sessions

MAX_BYTES = 12_000_000
MAX_ROWS = 100_000


def load_daily_sessions(
    path: str | Path, *, calendar: SessionCalendar, expected_calendar_sha256: str,
    instrument: str, quote_currency: str, captured_at_utc: datetime,
    available_at_utc: datetime, decision_at_utc: datetime,
) -> ResearchDataset:
    """Reject any absent/extra session, changed calendar, or late data availability.

    All source/calendar labels and timestamps remain *unverified assertions*.
    """
    if not expected_calendar_sha256 or calendar.calendar_sha256 != expected_calendar_sha256:
        raise ValueError("Calendar fingerprint missing or mismatch")
    if not instrument or len(instrument) > 64 or not instrument.replace("-", "").replace(".", "").isalnum():
        raise ValueError("Invalid instrument identifier")
    if quote_currency not in {"USD", "AUD", "EUR"}:
        raise ValueError("Unsupported explicit quote currency")
    raw = Path(path).read_bytes()
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Empty or oversized daily CSV")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("Daily CSV is not UTF-8") from exc
    reader = csv.DictReader(decoded.splitlines())
    required = {"session_date", "open", "high", "low", "close", "volume"}
    if not reader.fieldnames or set(reader.fieldnames) != required:
        raise ValueError("Exact daily CSV schema required")
    bars = []
    for idx, row in enumerate(reader, 2):
        if len(bars) >= MAX_ROWS:
            raise ValueError("Daily CSV exceeds row limit")
        try:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("Malformed CSV column count")
            session = date.fromisoformat(row["session_date"])
            if row["session_date"] != session.isoformat():
                raise ValueError("Noncanonical session date")
            values = tuple(Decimal(row[key]) for key in ("open", "high", "low", "close", "volume"))
            o, h, l, c, v = values
            if not all(x.is_finite() for x in values):
                raise ValueError("Nonfinite OHLCV")
            if min(o, h, l, c) <= 0 or v < 0 or l > min(o, c) or h < max(o, c):
                raise ValueError("Inconsistent OHLCV")
            bars.append(CanonicalOHLCV(
                datetime(session.year, session.month, session.day, tzinfo=timezone.utc),
                o, h, l, c, v))
        except (ValueError, TypeError, InvalidOperation, OverflowError) as exc:
            raise ValueError(f"Invalid daily CSV row {idx}: {exc}") from exc
    if len(bars) < 80:
        raise ValueError("At least 80 daily sessions required")
    digest = hashlib.sha256(raw).hexdigest()
    manifest = {
        "schema": "alpha-labs.daily-session.v1",
        "csv_sha256": digest,
        "calendar_sha256": calendar.calendar_sha256,
        "calendar_source": calendar.calendar_source,
        "venue": calendar.venue,
        "instrument": instrument,
        "quote_currency": quote_currency,
        "interval_minutes": 1440,
        "candle_count": len(bars),
        "price_source_authenticated": False,
        "independent_price_verification": False,
        "trading_enabled": False,
        "source_class": "user-supplied",
        "calendar_source_authenticated": False,
        "point_in_time_attested": False,
        "commercial_rights_verified": False,
    }
    record = ResearchDataset(tuple(bars), manifest, digest)
    validate_daily_sessions(record, calendar)
    PointInTimeRecord(digest, captured_at_utc, available_at_utc, decision_at_utc).validate(record)
    # Date labels denote trading sessions, not actual bar publication timestamps.
    # Requiring capture >= last session date is necessary, not sufficient, for PIT.
    return record


def verify_daily_sessions(
    path: str | Path, record: ResearchDataset, *, calendar: SessionCalendar,
    captured_at_utc: datetime, available_at_utc: datetime,
    decision_at_utc: datetime,
) -> None:
    """Reparse original bytes and compare the full canonical record fail closed."""
    if record.verified_prices or record.trading_enabled:
        raise ValueError("Research-only records required")
    expected = load_daily_sessions(
        path, calendar=calendar,
        expected_calendar_sha256=record.manifest["calendar_sha256"],
        instrument=record.manifest["instrument"],
        quote_currency=record.manifest["quote_currency"],
        captured_at_utc=captured_at_utc, available_at_utc=available_at_utc,
        decision_at_utc=decision_at_utc)
    if expected != record:
        raise ValueError("Daily data, calendar provenance or canonical observations changed")
