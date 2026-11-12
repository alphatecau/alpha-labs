"""Continuous public quote polling independent of web requests."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event, Lock, Thread

from alpha_lab.research.coinbase_paper_book import PRODUCTS, executable, fetch_book


class PaperMarketFeed:
    def __init__(self, *, fetch=fetch_book, clock=lambda: datetime.now(timezone.utc)):
        self.fetch = fetch
        self.clock = clock
        self.lock = Lock()
        self.quotes = {}
        self.failed = set(PRODUCTS)
        self.history = {product: deque(maxlen=300) for product in PRODUCTS}
        self.stop = Event()
        self.thread = None
        self.watchdog = None

    def poll(self, pool):
        pending = {product: pool.submit(self.fetch, product) for product in PRODUCTS}
        received = {}
        for product, result in pending.items():
            try:
                quote = result.result()
                if quote.symbol == product and executable(quote, self.clock()):
                    received[product] = quote
            except Exception:
                # Protocol failures cannot leave an old book healthy or kill polling.
                continue
        with self.lock:
            self.failed = set(PRODUCTS)
            for product, quote in received.items():
                previous = self.quotes.get(product)
                if previous and (quote.source_sequence < previous.source_sequence
                                 or quote.exchange_at < previous.exchange_at):
                    continue
                if previous and quote.source_sequence == previous.source_sequence:
                    if (quote.bid, quote.ask, quote.bid_size, quote.ask_size) != (
                            previous.bid, previous.ask, previous.bid_size, previous.ask_size):
                        continue
                self.quotes[product] = quote
                self.failed.discard(product)
                if previous is None or quote.exchange_at > previous.exchange_at:
                    self.history[product].append((quote.source_timestamp, str(quote.mid)))

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
