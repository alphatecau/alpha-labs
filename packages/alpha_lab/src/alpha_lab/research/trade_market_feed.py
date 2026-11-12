"""Bounded background refresh of closed candles for the read-only research API."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from threading import Event, Lock, Thread
from urllib.error import HTTPError

from alpha_lab.data.adapters.coinbase_candles import (
    HTTP_TIMEOUT_SECONDS, fetch_product_rules, fetch_recent_candles, latest_candle_end,
)
from alpha_lab.research.coinbase_paper_book import PRODUCTS

PROVIDER_ERRORS = (OSError, HTTPException, ValueError, ArithmeticError, RecursionError)
REFRESH_SECONDS = 60
METADATA_MAX_AGE = timedelta(minutes=15)


def retry_delay(error, now):
    """Read the two Retry-After forms. A missing header uses a bounded backoff."""
    if not isinstance(error, HTTPError) or error.code != 429:
        return None
    raw = (error.headers.get("Retry-After") or "").strip() if error.headers else ""
    if raw.isascii() and raw.isdecimal() and len(raw) <= 9:
        return max(REFRESH_SECONDS, int(raw))
    if raw and len(raw) <= 80:
        try:
            when = parsedate_to_datetime(raw)
            if when.utcoffset() is not None:
                return max(REFRESH_SECONDS, (when - now).total_seconds())
        except (ValueError, TypeError, OverflowError):
            pass
    return REFRESH_SECONDS


class TradeCandleFeed:
    """One cached timeframe. No provider calls on web request threads."""

    def __init__(self, *, timeframe="4h", fetch=fetch_recent_candles, fetch_rules=fetch_product_rules,
                 clock=lambda: datetime.now(timezone.utc)):
        latest_candle_end(clock(), timeframe)
        self.timeframe, self.fetch, self.fetch_rules, self.clock = timeframe, fetch, fetch_rules, clock
        self.lock = Lock()
        self.stop = Event()
        self.thread = None
        self.batches = {}
        self.metadata = {}
        self.cooldown_until = None

    def poll(self):
        now = self.clock()
        end = latest_candle_end(now, self.timeframe)
        with self.lock:
            if self.cooldown_until is not None and now < self.cooldown_until:
                return
            batches, metadata = dict(self.batches), dict(self.metadata)
        for product in PRODUCTS:
            if self.stop.is_set():
                return
            try:
                batch = batches.get(product)
                if batch is None or batch.end != end:
                    batch = self.fetch(product, now, timeframe=self.timeframe)
                    if batch.product != product or batch.timeframe != self.timeframe or batch.end != end:
                        raise ValueError("unexpected candle batch identity")
                    with self.lock:
                        self.batches[product] = batch
                if self.stop.is_set():
                    return
                rules, observed = metadata.get(product, (None, None))
                if rules is None or not timedelta(0) <= now - observed < METADATA_MAX_AGE:
                    rules = self.fetch_rules(product)
                    if rules.product != product:
                        raise ValueError("unexpected product rules identity")
                    with self.lock:
                        self.metadata[product] = (rules, now)
            except PROVIDER_ERRORS as exc:
                delay = retry_delay(exc, self.clock())
                with self.lock:
                    if delay is not None:
                        self.cooldown_until = self.clock() + timedelta(seconds=delay)
                    self.metadata.pop(product, None)
                if delay is not None:
                    return

    def snapshot(self, now):
        end = latest_candle_end(now, self.timeframe)
        with self.lock:
            if self.cooldown_until is not None and now < self.cooldown_until:
                return {}, {}, "PROVIDER_RATE_LIMITED"
            return ({product: batch for product, batch in self.batches.items() if batch.end == end},
                    {product: rules for product, (rules, observed) in self.metadata.items()
                     if timedelta(0) <= now - observed < METADATA_MAX_AGE}, "PUBLIC")

    def start(self):
        if self.thread is not None or self.stop.is_set():
            raise RuntimeError("candle feed is single-use")

        def run():
            while not self.stop.is_set():
                self.poll()
                self.stop.wait(REFRESH_SECONDS)

        self.thread = Thread(target=run, name="alpha-trade-candles", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=HTTP_TIMEOUT_SECONDS + 2)
            if self.thread.is_alive():
                raise RuntimeError("trade candle worker has not stopped")
