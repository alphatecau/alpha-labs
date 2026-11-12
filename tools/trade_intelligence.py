"""Read public spot data or reproduce a development walk-forward report."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from functools import partial
from hashlib import sha256
from pathlib import Path
from time import sleep
from urllib.error import HTTPError

from alpha_lab.data.adapters.coinbase_candles import (
    SOURCE, check_research_window, fetch_candles, parse_candles, utc,
)
from alpha_lab.research.coinbase_paper_book import PRODUCTS, fetch_book
from alpha_lab.research.paper_market_feed import PaperMarketFeed
from alpha_lab.research.trade_intelligence import analyse_trade_intelligence, utc_now
from alpha_lab.research.trade_market_feed import TradeCandleFeed, retry_delay
from alpha_lab.research.trade_walk_forward import walk_forward

CHUNK = timedelta(hours=288)
MIN_HISTORY = timedelta(days=18)
MAX_HISTORY = timedelta(days=120)
CAPTURE_SOURCE = "Local OHLCV replay capture"


def _live(timeframe):
    candles = TradeCandleFeed(timeframe=timeframe)
    quotes = PaperMarketFeed(fetch=partial(fetch_book, timeout=20))
    candles.poll()
    with ThreadPoolExecutor(max_workers=len(PRODUCTS)) as pool:
        quotes.poll(pool)
    now = utc_now()
    books, healthy, _ = quotes.snapshot(now)
    batches, rules, status = candles.snapshot(now)
    return analyse_trade_intelligence(now=now, quotes=books, healthy=healthy, batches=batches,
                                      rules=rules, timeframe=timeframe, provider_state=status)


def _download(product, start, end):
    rows, digests = [], []
    for cursor in _windows(start, end):
        limit = min(end, cursor + CHUNK)
        try:
            batch = fetch_candles(product, start=cursor, end=limit, timeframe="1h")
        except HTTPError as exc:
            delay = retry_delay(exc, utc_now())
            if delay is None or delay > 60:
                raise
            sleep(delay)
            batch = fetch_candles(product, start=cursor, end=limit, timeframe="1h")
        rows.extend([int(bar.time.timestamp()), *(str(x) for x in
                    (bar.low, bar.high, bar.open, bar.close, bar.volume))] for bar in batch.bars)
        digests.append(batch.sha256)
        sleep(0.15)
    return {"product": product, "start_utc": start.isoformat(), "end_utc": end.isoformat(),
            "provider_response_sha256": digests, "ohlcv": rows}


def _windows(start, end):
    for offset in range(0, (end - start) // timedelta(hours=1), CHUNK // timedelta(hours=1)):
        yield start + timedelta(hours=offset)


def _validate_capture(capture, product, start, end):
    if (capture.get("product") != product or capture.get("start_utc") != start.isoformat()
            or capture.get("end_utc") != end.isoformat()):
        raise ValueError("capture product or time bounds do not match the request")
    rows = capture["ohlcv"]
    if not isinstance(rows, list) or len(rows) != (end - start) // timedelta(hours=1):
        raise ValueError("capture does not match the expected number of hourly bars")
    bars = []
    for offset, cursor in enumerate(_windows(start, end)):
        index = offset * (CHUNK // timedelta(hours=1))
        bars.extend(parse_candles(rows[index:index + CHUNK // timedelta(hours=1)], start=cursor,
                                  end=min(end, cursor + CHUNK), timeframe="1h"))
    return tuple(bars)


def _historical(start, end, *, capture_dir, replay_dir):
    check_research_window(start, end)
    if (not MIN_HISTORY <= end - start <= MAX_HISTORY
            or any(int(stamp.timestamp()) % 14400 or stamp.microsecond for stamp in (start, end))):
        raise ValueError("historical request must span 18–120 days on UTC four-hour boundaries")
    if end >= utc_now():
        raise ValueError("historical data must precede the current UTC time")
    if capture_dir:
        capture_dir.mkdir(parents=True, exist_ok=True)
    def evaluate(product):
        filename = f"{product}.json"
        if replay_dir:
            with (replay_dir / filename).open("rb") as stream:
                raw = stream.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("capture exceeds size limit")
            capture = json.loads(raw)
        else:
            capture = _download(product, start, end)
        bars = _validate_capture(capture, product, start, end)
        canonical = json.dumps(capture, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        if capture_dir:
            with (capture_dir / filename).open("xb") as stream:
                stream.write(canonical + b"\n")
        result = walk_forward(product, bars, source=CAPTURE_SOURCE if replay_dir else SOURCE,
                              capture_sha256=sha256(canonical).hexdigest())
        return {**result, "verified_https_capture": replay_dir is None}

    with ThreadPoolExecutor(max_workers=len(PRODUCTS)) as pool:
        results = list(pool.map(evaluate, PRODUCTS))
    return {"mode": "DEVELOPMENT_WALK_FORWARD", "assets": results, "automated_paper_execution": False,
            "real_money_execution": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--live", action="store_true")
    operation.add_argument("--walk-forward", nargs=2, metavar=("START_UTC", "END_UTC"))
    parser.add_argument("--timeframe", choices=("4h", "1d"), default="4h")
    storage = parser.add_mutually_exclusive_group()
    storage.add_argument("--capture-dir", type=Path)
    storage.add_argument("--replay-dir", type=Path)
    args = parser.parse_args()
    try:
        if args.live:
            if args.capture_dir or args.replay_dir:
                parser.error("capture and replay options require --walk-forward")
            result = _live(args.timeframe)
        else:
            if args.timeframe != "4h":
                parser.error("walk-forward is scoped to four-hour strategies")
            start, end = (utc(datetime.fromisoformat(value)) for value in args.walk_forward)
            result = _historical(start, end, capture_dir=args.capture_dir, replay_dir=args.replay_dir)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f"Trade intelligence unavailable ({type(exc).__name__}): {exc}\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
