"""Published 2026 regular-session calendar. Research only.

Sources:
https://www.nyse.com/trade/hours-calendars
https://nasdaqtrader.com/Trader.aspx?id=Calendar

Snapshot checked 2026-11-07. Unscheduled closures,
subsequent exchange alerts and source revisions are
not monitored automatically.
"""
from datetime import date, time, timedelta

from alpha_lab.data.equity_sessions import (
    USSession, verify_equity_bars
)

CLOSED = frozenset(date(2026, m, d) for m, d in (
    (1, 1), (1, 19), (2, 16), (4, 3),
    (5, 25), (6, 19), (7, 3), (9, 7),
    (11, 26), (12, 25)
))

EARLY = frozenset((
    date(2026, 11, 27),
    date(2026, 12, 24),
))


def sessions_2026(calendar, start, end):
    if calendar not in {"XNYS", "XNAS"}:
        raise ValueError("Unsupported exchange")
    if type(start) is not date or type(end) is not date:
        raise ValueError("Invalid date type")
    if start.year != 2026 or end.year != 2026:
        raise ValueError("Calendar coverage limited to 2026")
    if start > end:
        raise ValueError("Invalid date range")

    result = []
    day = start
    while day <= end:
        if day.weekday() < 5 and day not in CLOSED:
            close = time(13) if day in EARLY else time(16)
            result.append(USSession.from_et(calendar, day, close))
        day += timedelta(days=1)
    return tuple(result)


def verify_official_2026_bars(
    instrument, start, end, bars, minutes=30
):
    schedule = sessions_2026(instrument.calendar, start, end)
    if not schedule:
        raise ValueError("No scheduled sessions")
    return verify_equity_bars(
        instrument, schedule, bars, minutes=minutes
    )
