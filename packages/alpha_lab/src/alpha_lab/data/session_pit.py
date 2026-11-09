"""Offline, fail-closed exchange-session and point-in-time research checks.

Explicit independently supplied session dates are required; no holiday calendar is
inferred and no external source or trading endpoint is contacted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from typing import Sequence

from alpha_lab.data.provider_neutral import ResearchDataset

UTC = timezone.utc


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class SessionCalendar:
    venue: str
    session_dates: tuple[date, ...]
    calendar_source: str
    calendar_sha256: str

    @classmethod
    def from_explicit_dates(cls, *, venue: str, session_dates: Sequence[date],
                            calendar_source: str) -> "SessionCalendar":
        if not venue or not calendar_source or len(venue) > 64 or len(calendar_source) > 128:
            raise ValueError("Explicit venue and calendar source required")
        if not session_dates or len(session_dates) > 100000:
            raise ValueError("Bounded nonempty session calendar required")
        dates = tuple(session_dates)
        if any(type(d) is not date for d in dates):
            raise ValueError("Calendar must contain date objects")
        if tuple(sorted(set(dates))) != dates:
            raise ValueError("Calendar dates must be strictly increasing and unique")
        digest = hashlib.sha256(json.dumps([d.isoformat() for d in dates],
                                          separators=(",", ":")).encode()).hexdigest()
        return cls(venue, dates, calendar_source, digest)


def validate_daily_sessions(dataset: ResearchDataset, calendar: SessionCalendar) -> None:
    """Require exactly one UTC daily bar per explicit session, without weekend guesses."""
    if dataset.verified_prices or dataset.trading_enabled:
        raise ValueError("Research-only dataset required")
    if dataset.manifest["interval_minutes"] != 1440:
        raise ValueError("Daily interval required")
    if dataset.manifest["venue"] != calendar.venue:
        raise ValueError("Venue mismatch")
    actual = tuple(b.timestamp_utc.date() for b in dataset.bars)
    if actual != calendar.session_dates:
        raise ValueError("Missing, extra, duplicated or unordered exchange sessions")
    if any(b.timestamp_utc.tzinfo != UTC or b.timestamp_utc.time().isoformat() != "00:00:00"
           for b in dataset.bars):
        raise ValueError("Expected UTC session-date midnight bar labels")


@dataclass(frozen=True)
class PointInTimeRecord:
    source_sha256: str
    captured_at_utc: datetime
    available_at_utc: datetime
    decision_at_utc: datetime
    source_authenticated: bool = False
    commercial_rights_verified: bool = False

    def validate(self, dataset: ResearchDataset) -> None:
        if self.source_authenticated or self.commercial_rights_verified:
            raise ValueError("Unsupported authenticity or licensing assertion")
        capture = _utc(self.captured_at_utc, "capture")
        available = _utc(self.available_at_utc, "availability")
        decision = _utc(self.decision_at_utc, "decision")
        if not (capture <= available <= decision):
            raise ValueError("Data was not demonstrably available before decision")
        if self.source_sha256 != dataset.manifest["csv_sha256"]:
            raise ValueError("Source digest mismatch")
        if not dataset.bars:
            raise ValueError("Empty research dataset")
        if dataset.bars[-1].timestamp_utc > capture:
            raise ValueError("Observations postdate capture")
        if dataset.verified_prices or dataset.trading_enabled:
            raise ValueError("Research-only data required")
