"""Session-aware, USD-only 2026 equity CSV import; offline research only."""
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from io import StringIO
from pathlib import Path

from alpha_lab.data.csv_import import Bar, Dataset
from alpha_lab.data.exchange_calendar_2026 import verify_official_2026_bars
from alpha_lab.domain.assets import AssetClass, Instrument

COLUMNS = ('timestamp', 'open', 'high', 'low', 'close', 'volume')


@dataclass(frozen=True)
class EquityImport:
    instrument: Instrument
    dataset: Dataset
    start: date
    end: date
    source_id: str
    retrieved_at_utc: datetime
    source_authenticated: bool = False
    corporate_actions_verified: bool = False
    trading_enabled: bool = False


def load_equity_csv(path, *, instrument, start, end,
                    source_id, retrieved_at_utc):
    if instrument.asset_class not in (AssetClass.US_EQUITY, AssetClass.US_ETF):
        raise ValueError('US equity or ETF required')
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError('Explicit data source ID required')
    if (type(retrieved_at_utc) is not datetime or
            retrieved_at_utc.utcoffset() != timedelta(0)):
        raise ValueError('UTC retrieval timestamp required')

    raw = Path(path).read_bytes()
    reader = csv.DictReader(StringIO(raw.decode('utf-8-sig')))
    if reader.fieldnames != list(COLUMNS):
        raise ValueError('Expected timestamp,open,high,low,close,volume')

    bars = []
    for line, row in enumerate(reader, 2):
        try:
            if (None in row or
                    not all(isinstance(row.get(k), str) and row[k] for k in COLUMNS)):
                raise ValueError('Missing or extra field')
            stamp = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
            if stamp.utcoffset() != timedelta(0):
                raise ValueError('Candle timestamp must be UTC')
            o, h, l, c, v = (Decimal(row[k]) for k in COLUMNS[1:])
            if (not all(x.is_finite() for x in (o, h, l, c, v)) or
                    min(o, h, l, c) <= 0 or v < 0 or
                    l > min(o, c) or h < max(o, c) or l > h):
                raise ValueError('Invalid OHLCV')
            bars.append(Bar(stamp.astimezone(timezone.utc), o, h, l, c, v))
        except (ValueError, TypeError, ArithmeticError) as exc:
            raise ValueError(f'Invalid CSV row {line}: {exc}') from exc

    verify_official_2026_bars(instrument, start, end, bars, minutes=30)
    if retrieved_at_utc < bars[-1].time + timedelta(minutes=30):
        raise ValueError('Retrieval predates last candle close')

    dataset = Dataset(tuple(bars), 'USD', sha256(raw).hexdigest(), source_id, 30)
    return EquityImport(instrument, dataset, start, end, source_id,
                        retrieved_at_utc)
