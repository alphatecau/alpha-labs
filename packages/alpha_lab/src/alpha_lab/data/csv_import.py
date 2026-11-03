"""Strict, point-in-time OHLCV CSV ingestion. Import does not authenticate market prices."""
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import hashlib

@dataclass(frozen=True)
class Bar:
    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

@dataclass(frozen=True)
class Dataset:
    bars: tuple[Bar, ...]
    quote_currency: str
    sha256: str
    provenance: str
    interval_minutes: int


def load_csv(path: str | Path, *, quote_currency: str, interval_minutes: int = 60,
             provenance: str = 'user-supplied-unverified') -> Dataset:
    path = Path(path)
    if interval_minutes <= 0:
        raise ValueError('interval_minutes must be positive')
    if quote_currency.upper() not in {'USD', 'USDC', 'AUD', 'USDT', 'EUR'}:
        raise ValueError('Explicit supported quote currency required; no FX conversion is assumed')
    raw=path.read_bytes()
    bars=[]
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or not {'timestamp','open','high','low','close','volume'}.issubset(reader.fieldnames):
            raise ValueError('CSV must contain timestamp,open,high,low,close,volume')
        for n,row in enumerate(reader,2):
            try:
                stamp=datetime.fromisoformat(row['timestamp'].replace('Z','+00:00'))
                if stamp.tzinfo is None: raise ValueError('timestamp timezone missing')
                stamp=stamp.astimezone(timezone.utc)
                O,H,L,C,V=[Decimal(row[col]) for col in ('open','high','low','close','volume')]
                if not all(x.is_finite() for x in (O,H,L,C,V)): raise ValueError('nonfinite value')
                if min(O,H,L,C) <= 0 or V < 0 or L>min(O,C) or H<max(O,C) or L>H:
                    raise ValueError('invalid OHLCV values')
                if bars:
                    dt=(stamp-bars[-1].time).total_seconds()
                    if dt <= 0: raise ValueError('duplicate or unordered timestamps')
                    if dt != interval_minutes*60: raise ValueError('missing/irregular candle interval')
                bars.append(Bar(stamp,O,H,L,C,V))
            except (KeyError, TypeError, InvalidOperation, ValueError) as exc:
                raise ValueError(f'Invalid market row {n}: {exc}') from exc
    if len(bars)<80: raise ValueError('At least 80 complete candles required')
    return Dataset(tuple(bars),quote_currency.upper(),hashlib.sha256(raw).hexdigest(),provenance,interval_minutes)
