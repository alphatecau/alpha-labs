"""US regular-session validation. Research only.

Session dates and early closes must be checked against an
authoritative exchange calendar. This module does not
authenticate the supplied calendar or market prices.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from alpha_lab.domain.assets import AssetClass

ET = ZoneInfo("America/New_York")
CALENDARS = {"XNYS", "XNAS"}


@dataclass(frozen=True)
class USSession:
    calendar: str
    day: date
    opens_utc: datetime
    closes_utc: datetime

    @classmethod
    def from_et(cls, calendar, day, close_et=time(16)):
        if calendar not in CALENDARS:
            raise ValueError("Unsupported calendar")
        if not isinstance(day, date) or isinstance(day, datetime):
            raise ValueError("Invalid session date")
        if day.weekday() >= 5 or close_et not in (time(13), time(16)):
            raise ValueError("Invalid session configuration")
        opened = datetime.combine(day, time(9, 30), ET)
        closed = datetime.combine(day, close_et, ET)
        return cls(
            calendar, day,
            opened.astimezone(timezone.utc),
            closed.astimezone(timezone.utc),
        )


def verify_equity_bars(instrument, sessions, bars, minutes=30):
    """Validate complete UTC candle coverage of supplied sessions."""
    if instrument.asset_class not in (
        AssetClass.US_EQUITY, AssetClass.US_ETF
    ):
        raise ValueError("Equity or ETF required")
    if type(minutes) is not int or minutes <= 0:
        raise ValueError("Invalid interval")

    sessions = tuple(sessions)
    bars = tuple(bars)
    if not sessions or not bars:
        raise ValueError("Empty data or session schedule")

    expected = []
    previous_close = None
    step = timedelta(minutes=minutes)

    for session in sessions:
        if not isinstance(session, USSession):
            raise ValueError("Invalid session")
        if session.calendar != instrument.calendar:
            raise ValueError("Calendar mismatch")

        span = session.closes_utc - session.opens_utc
        close_et = time(13) if span == timedelta(
            hours=3, minutes=30
        ) else time(16)

        if session != USSession.from_et(
            session.calendar, session.day, close_et
        ):
            raise ValueError("Invalid session boundaries")
        if previous_close is not None:
            if session.opens_utc <= previous_close:
                raise ValueError("Unordered sessions")
        if span.total_seconds() % step.total_seconds():
            raise ValueError("Interval does not fit session")

        count = int(span / step)
        expected.extend(
            session.opens_utc + i * step
            for i in range(count)
        )
        previous_close = session.closes_utc

    if len(expected) != len(bars):
        raise ValueError("Missing or extra bars")
    if any(bar.time != stamp for bar, stamp in zip(bars, expected)):
        raise ValueError("Misaligned or out-of-session bars")

    return len(bars)
