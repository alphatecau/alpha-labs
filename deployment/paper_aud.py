"""Value USD paper fills in AUD using prior published RBA F11.1 observations."""
import csv
import hashlib
import io
from bisect import bisect_left
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from alpha_lab.data.public_https import read_public_https

RBA = "https://www.rba.gov.au"
URL = RBA + "/statistics/tables/csv/f11.1-data.csv"


def utc(value):
    stamp = datetime.fromisoformat(value)
    if stamp.utcoffset() != timedelta(0):
        raise ValueError("UTC timestamp required")
    return stamp.astimezone(timezone.utc)


def rba_series():
    raw = read_public_https(URL, origin=RBA, max_bytes=2_000_000, timeout=6)
    rows = iter(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    column = next(row.index("FXRUSD") for row in rows if row and row[0] == "Series ID")
    rates = {}
    for row in rows:
        if len(row) <= column or not row[column].strip():
            continue
        day = datetime.strptime(row[0], "%d-%b-%Y").date()
        rate = Decimal(row[column])
        if day in rates or not rate.is_finite() or rate <= 0:
            raise ValueError("invalid RBA series")
        rates[day] = rate
    return rates, hashlib.sha256(raw).hexdigest()


def aud_result(fills, snapshot, as_of, series):
    """Realised FIFO and fees at each fill's FX. Report USD cash translated separately."""
    rates, digest = series
    dates = sorted(rates)
    used = {}

    def rate_at(stamp):
        day = stamp.date()
        i = bisect_left(dates, day) - 1  # Strictly prior day avoids publication-time look-ahead.
        if i < 0 or (day - dates[i]).days > 7:
            raise ValueError("compatible FX unavailable")
        date = dates[i]
        used[date.isoformat()] = str(rates[date])
        return rates[date]

    valuation_rate = rate_at(as_of)
    lots = defaultdict(deque)
    marks = {}
    realised = fees = Decimal(0)
    for fill in fills:
        when = utc(fill["filled_at"])
        if when > as_of:
            raise ValueError("fill follows snapshot cutoff")
        fx = rate_at(when)
        symbol = fill["symbol"]
        qty, price, fee = (Decimal(fill[k]) for k in ("quantity", "price", "fee"))
        marks[symbol] = price / valuation_rate
        price, fee = price / fx, fee / fx
        fees += fee
        if fill["side"] == "BUY":
            lots[symbol].append([qty, price + fee / qty])
            continue
        realised += qty * price - fee
        while qty:
            lot = lots[symbol][0]
            matched = min(lot[0], qty)
            realised -= matched * lot[1]
            qty -= matched
            lot[0] -= matched
            if not lot[0]:
                lots[symbol].popleft()
    unrealised = sum((qty * (marks[s] - basis) for s, queue in lots.items()
                      for qty, basis in queue), Decimal(0))
    return {"realised": str(realised), "unrealised": str(unrealised), "fees": str(fees),
            "cash": str(Decimal(snapshot["cash_usd"]) / valuation_rate),
            "equity": str(Decimal(snapshot["nav_usd"]) / valuation_rate),
            "source": "RBA F11.1 FXRUSD", "source_url": URL, "sha256": digest,
            "usd_per_aud": used, "valuation": "OFFLINE_LAST_FILL_MARKS"}
