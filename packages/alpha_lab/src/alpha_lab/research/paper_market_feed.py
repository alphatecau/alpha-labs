"""Continuous public quote polling independent of web requests."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from threading import Event, Lock, Thread
from time import monotonic
from urllib.error import HTTPError

from alpha_lab.research.coinbase_paper_book import PRODUCTS, executable, fetch_book


class PaperMarketFeed:
    def __init__(self, *, fetch=fetch_book, clock=lambda: datetime.now(timezone.utc),
                 retry_clock=monotonic):
        self.fetch = fetch
        self.clock = clock
        self.retry_clock = retry_clock
        self.lock = Lock()
        self.quotes = {}
        self.failed = set(PRODUCTS)
        self.retry_at = 0
        self.failures = dict.fromkeys(PRODUCTS, 0)
        self.product_retry_at = dict.fromkeys(PRODUCTS, 0)
        self.history = {product: deque(maxlen=300) for product in PRODUCTS}
        self.stop = Event()
        self.thread = None
        self.watchdog = None

    def poll(self, pool):
        with self.lock:
            now = self.retry_clock()
            if now < self.retry_at:
                return
            products = [product for product in PRODUCTS if now >= self.product_retry_at[product]]
        pending = {pool.submit(self.fetch, product): product for product in products}
        for result in as_completed(pending):
            product = pending[result]
            try:
                quote = result.result()
                if quote.symbol != product or not executable(quote, self.clock()):
                    raise ValueError("unverified market quote")
            except Exception as exc:
                self._record_failure(product, exc)
                continue
            with self.lock:
                if self.retry_clock() < self.retry_at:
                    continue
                previous = self.quotes.get(product)
                if previous and (quote.source_sequence < previous.source_sequence
                                 or quote.exchange_at < previous.exchange_at):
                    self.failed.add(product)
                    continue
                if previous and quote.source_sequence == previous.source_sequence:
                    if (quote.bid, quote.ask, quote.bid_size, quote.ask_size) != (
                            previous.bid, previous.ask, previous.bid_size, previous.ask_size):
                        self.failed.add(product)
                        continue
                self.quotes[product] = quote
                self.failed.discard(product)
                self.failures[product] = 0
                if previous is None or quote.exchange_at > previous.exchange_at:
                    self.history[product].append((quote.source_timestamp, str(quote.mid)))

    def _record_failure(self, product, exc):
        with self.lock:
            now = self.retry_clock()
            self.failed.add(product)
            self.failures[product] += 1
            if self.failures[product] >= 3:
                self.product_retry_at[product] = now + min(60, 2 ** min(6, self.failures[product]))
            if isinstance(exc, HTTPError) and exc.code == 429:
                header = (exc.headers.get("Retry-After") or "").strip() if exc.headers else ""
                delay = min(300, max(10, int(header))) if header.isascii() and header.isdecimal() and len(header) <= 6 else 30
                self.retry_at = max(self.retry_at, now + delay)
                self.failed.update(PRODUCTS)

    def snapshot(self, now):
        with self.lock:
            quotes = dict(self.quotes)
            healthy = {product: product not in self.failed and product in quotes
                       and executable(quotes[product], now) for product in PRODUCTS}
            return quotes, healthy, {product: list(series) for product, series in self.history.items()}

    def start(self, on_poll, *, watchdog_interval=1):
        if self.thread is not None:
            raise RuntimeError("quote polling already started")
        if not callable(on_poll) or not 0 < watchdog_interval <= 1:
            raise ValueError("bounded health watchdog required")

        def notify():
            try:
                on_poll()
            except Exception:
                with self.lock:
                    self.failed = set(PRODUCTS)

        def run():
            with ThreadPoolExecutor(max_workers=len(PRODUCTS)) as pool:
                while not self.stop.is_set():
                    try:
                        self.poll(pool)
                    except Exception:
                        with self.lock:
                            self.failed = set(PRODUCTS)
                    notify()
                    self.stop.wait(2)

        def watch():
            # Staleness HALT must not wait for a blocked network poll to finish.
            while not self.stop.wait(watchdog_interval):
                notify()

        self.thread = Thread(target=run, name="alpha-paper-market-feed", daemon=True)
        self.watchdog = Thread(target=watch, name="alpha-paper-health-watchdog", daemon=True)
        self.thread.start()
        self.watchdog.start()

    def close(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=10)
            self.watchdog.join(timeout=10)
            if self.thread.is_alive() or self.watchdog.is_alive():
                raise RuntimeError("paper feed has not stopped; keep execution halted")
