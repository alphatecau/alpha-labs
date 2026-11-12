"""Closed Coinbase Exchange spot candles and product constraints."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from urllib.parse import urlencode

from alpha_lab.data.csv_import import Bar
from alpha_lab.data.public_https import decode_public_json, read_public_https
from alpha_lab.research.coinbase_paper_book import BASE_URL, PRODUCTS

SOURCE = "Coinbase Exchange OHLCV"
HTTP_TIMEOUT_SECONDS = 25
BARS_REQUIRED = 64
CLOSE_DELAY = timedelta(minutes=1)
INTERVALS = {"1h": (3600, 3600), "4h": (14400, 3600), "1d": (86400, 86400)}
SEALED_START = datetime(2027, 1, 1, tzinfo=timezone.utc)
SEALED_END = datetime(2028, 1, 1, tzinfo=timezone.utc)
MAX_PRICE_JUMP = Decimal("1.5")


@dataclass(frozen=True)
class CandleBatch:
    product: str
    timeframe: str
    bars: tuple[Bar, ...]
    end: datetime
    sha256: str
    source: str


@dataclass(frozen=True)
class ProductRules:
    product: str
    price_step: Decimal
    quantity_step: Decimal
    min_notional: Decimal


def utc(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("timezone-aware time required")
    return value.astimezone(timezone.utc)


def market_decimal(value):
    if type(value) not in (int, str, Decimal) or len(str(value)) > 40:
        raise ValueError("invalid market number")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid market decimal") from exc
    if (not result.is_finite() or result < 0 or result > Decimal("1e12")
            or result.as_tuple().exponent < -18):
        raise ValueError("market decimal outside bounds")
    return result


def interval(timeframe):
    try:
        return INTERVALS[timeframe]
    except (TypeError, KeyError) as exc:
        raise ValueError("unsupported timeframe") from exc


def latest_candle_end(now, timeframe):
    seconds, _ = interval(timeframe)
    epoch = int((utc(now) - CLOSE_DELAY).timestamp())
    return datetime.fromtimestamp(epoch - epoch % seconds, timezone.utc)


def check_research_window(start, end):
    if utc(start) >= utc(end):
        raise ValueError("invalid research window")
    if start < SEALED_END and end > SEALED_START:
        raise ValueError("reserved evaluation window")


def check_cadence(bars, seconds):
    step = timedelta(seconds=seconds)
    for previous, current in zip(bars, bars[1:]):
        if current.time - previous.time != step:
            raise ValueError("missing or duplicate candle")
        if max(current.open, previous.close) > min(current.open, previous.close) * MAX_PRICE_JUMP:
            raise ValueError("candle gap price outlier")


def parse_candles(payload, *, start, end, timeframe):
    """Parse only the requested half-open window. Open bars cannot enter features."""
    start, end = utc(start), utc(end)
    check_research_window(start, end)
    seconds, provider_seconds = interval(timeframe)
    if (start.microsecond or end.microsecond or int(start.timestamp()) % seconds
            or int(end.timestamp()) % seconds):
        raise ValueError("unaligned candle request")
    count = int((end - start).total_seconds()) // provider_seconds
    if not 1 <= count <= 300 or type(payload) is not list or not 1 <= len(payload) <= 300:
        raise ValueError("invalid or oversized candle response")
    first, last = int(start.timestamp()), int(end.timestamp())
    rows = {}
    for row in payload:
        if type(row) is not list or len(row) != 6 or type(row[0]) is not int:
            raise ValueError("malformed candle")
        stamp = row[0]
        if not first <= stamp < last:
            continue
        if stamp in rows or stamp % provider_seconds:
            raise ValueError("duplicate or unaligned candle")
        low, high, open_, close, volume = map(market_decimal, row[1:])
        if not 0 < low <= min(open_, close) <= max(open_, close) <= high or volume <= 0:
            raise ValueError("invalid OHLCV values")
        if high > low * MAX_PRICE_JUMP:
            raise ValueError("candle range outlier")
        rows[stamp] = Bar(datetime.fromtimestamp(stamp, timezone.utc), open_, high, low, close, volume)
    if len(rows) != count:
        raise ValueError("missing completed candle")
    bars = tuple(rows[stamp] for stamp in sorted(rows))
    check_cadence(bars, provider_seconds)
    return aggregate_bars(bars, seconds // provider_seconds)


def aggregate_bars(bars, group):
    if group == 1:
        return bars
    if not bars or len(bars) % group:
        raise ValueError("aggregation requires complete groups")
    groups = (bars[i:i + group] for i in range(0, len(bars), group))
    return tuple(Bar(bucket[0].time, bucket[0].open, max(b.high for b in bucket),
                     min(b.low for b in bucket), bucket[-1].close,
                     sum(b.volume for b in bucket)) for bucket in groups)


def fetch_candles(product, *, start, end, timeframe="4h", opener=None):
    if product not in PRODUCTS:
        raise ValueError("unsupported product")
    start, end = utc(start), utc(end)
    check_research_window(start, end)
    seconds, provider_seconds = interval(timeframe)
    if (start.microsecond or end.microsecond or int(start.timestamp()) % seconds
            or int(end.timestamp()) % seconds or end - start > timedelta(seconds=300 * provider_seconds)):
        raise ValueError("invalid candle request boundaries")
    query = urlencode({"start": start.isoformat().replace("+00:00", "Z"),
                       "end": end.isoformat().replace("+00:00", "Z"), "granularity": provider_seconds})
    raw = _read(f"/products/{product}/candles?{query}", 131072, opener)
    bars = parse_candles(decode_public_json(raw, parse_float=Decimal),
                         start=start, end=end, timeframe=timeframe)
    return CandleBatch(product, timeframe, bars, end, sha256(raw).hexdigest(), SOURCE)


def fetch_recent_candles(product, now, *, timeframe="4h", opener=None):
    seconds, _ = interval(timeframe)
    end = latest_candle_end(now, timeframe)
    return fetch_candles(product, start=end - timedelta(seconds=seconds * BARS_REQUIRED),
                         end=end, timeframe=timeframe, opener=opener)


def parse_product(product, data):
    if (product not in PRODUCTS or not isinstance(data, dict) or data.get("id") != product
            or data.get("quote_currency") != "USD" or data.get("base_currency") != product.split("-")[0]
            or data.get("status") != "online"
            or any(data.get(flag) is not False for flag in ("cancel_only", "post_only", "limit_only", "auction_mode"))
            or data.get("trading_disabled", False) is not False):
        raise ValueError("product metadata unavailable or market restricted")
    price, quantity, minimum = (market_decimal(data.get(field)) for field in
                                ("quote_increment", "base_increment", "min_market_funds"))
    if not (0 < price <= 1 and 0 < quantity <= 1 and minimum > 0):
        raise ValueError("invalid product precision or minimum")
    return ProductRules(product, price, quantity, minimum)


def fetch_product_rules(product, *, opener=None):
    if product not in PRODUCTS:
        raise ValueError("unsupported product")
    return parse_product(product, decode_public_json(_read(f"/products/{product}", 8192, opener)))


def _read(path, max_bytes, opener):
    return read_public_https(BASE_URL + path, origin=BASE_URL, max_bytes=max_bytes,
                             timeout=HTTP_TIMEOUT_SECONDS, content_types=("application/json",),
                             headers={"Cache-Control": "no-cache, no-store, max-age=0"}, opener=opener)
