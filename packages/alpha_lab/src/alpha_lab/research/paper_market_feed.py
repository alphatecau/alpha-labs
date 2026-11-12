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

    def poll(self, pool):
        pending = {product: pool.submit(self.fetch, product) for product in PRODUCTS}
        received = {}
        for product, result in pending.items():
            try:
                quote = result.result()
                if quote.symbol == product and executable(quote, self.clock()):
                    received[product] = quote
            except (OSError, ValueError, TypeError):
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

    def start(self, on_poll):
        if self.thread is not None:
            raise RuntimeError("quote polling already started")

        def run():
            with ThreadPoolExecutor(max_workers=len(PRODUCTS)) as pool:
                while not self.stop.is_set():
                    self.poll(pool)
                    on_poll()
                    self.stop.wait(2)

        self.thread = Thread(target=run, name="alpha-paper-market-feed", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join()
