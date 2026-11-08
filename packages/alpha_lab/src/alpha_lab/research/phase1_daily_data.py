"""Strict daily-bar data gates. No external download or fabricated ETF prices."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
import csv

CRYPTO=("BTCUSDT","ETHUSDT","SOLUSDT")
ETF=("SPY","QQQ","IWM","TLT","GLD","DBC","UUP")

def aggregate_crypto_utc_daily(bars):
    """Each daily candle requires exactly 24 consecutive UTC hourly bars."""
    if not bars or len(bars)%24:raise ValueError("Incomplete UTC daily history")
    days=[]
    for offset in range(0,len(bars),24):
        day=bars[offset:offset+24]
        midnight=day[0].time
        if days and midnight != bars[offset-24].time + timedelta(hours=24):
            raise ValueError("Gap between consecutive UTC daily candles")
        if midnight.tzinfo is None or midnight.utcoffset()!=timedelta(0) or midnight.hour!=0:
            raise ValueError("Daily UTC boundary mismatch")
        for j,b in enumerate(day):
            if b.time!=midnight+timedelta(hours=j):
                raise ValueError("Gap, duplicate or misordered crypto hour")
            if any(not Decimal(str(v)).is_finite() for v in (b.open,b.high,b.low,b.close,b.volume)) or b.volume<0 or b.low<=0 or b.high<max(b.open,b.close) or b.low>min(b.open,b.close):
                raise ValueError("Invalid OHLC")
        days.append({"date":midnight.date().isoformat(),"open":str(day[0].open),
                     "high":str(max(b.high for b in day)),
                     "low":str(min(b.low for b in day)),
                     "close":str(day[-1].close),
                     "volume":str(sum(b.volume for b in day))})
    return days

def verify_etf_csv(path,*,expected_symbol,expected_sha256,calendar_sessions):
    """Reject unknown session dates, unadjusted data, duplicates and tampered CSV.

    The session calendar must be externally verified and supplied by caller.
    This function does NOT certify calendar provenance or adjustment quality.
    """
    if expected_symbol not in ETF or not isinstance(expected_sha256,str) or len(expected_sha256)!=64 or not calendar_sessions:
        raise ValueError("Missing ETF provenance or calendar")
    path=Path(path)
    payload=path.read_bytes()
    if sha256(payload).hexdigest()!=expected_sha256:
        raise ValueError("ETF data checksum mismatch")
    try:
        reader=csv.DictReader(payload.decode("utf-8-sig").splitlines(), strict=True)
        rows=list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("Malformed ETF CSV") from exc
    if not rows:raise ValueError("Empty ETF dataset")
    required={"date","symbol","adjusted_close","volume","corporate_actions_verified"}
    if not required.issubset(reader.fieldnames or ()) or any(None in row for row in rows):
        raise ValueError("Missing required adjusted ETF fields")
    seen=set()
    last=None
    for r in rows:
        d=datetime.strptime(r["date"],"%Y-%m-%d").date()
        if d not in calendar_sessions or (last is not None and d<=last):
            raise ValueError("Invalid, duplicated or unsorted ETF session")
        if r["symbol"]!=expected_symbol or r["corporate_actions_verified"]!="true":
            raise ValueError("ETF corporate-action provenance unverified")
        try:
            px=Decimal(r["adjusted_close"]);vol=Decimal(r["volume"])
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("Invalid ETF adjusted close or volume") from exc
        if not px.is_finite() or px<=0 or not vol.is_finite() or vol<0:
            raise ValueError("Invalid ETF adjusted close or volume")
        seen.add(d);last=d
    if seen!=set(calendar_sessions):
        raise ValueError("Missing ETF sessions")
    return {"symbol":expected_symbol,"rows":len(rows),
            "sha256":expected_sha256,"verified_against_supplied_calendar":True,
            "calendar_provenance_independently_verified":False}
