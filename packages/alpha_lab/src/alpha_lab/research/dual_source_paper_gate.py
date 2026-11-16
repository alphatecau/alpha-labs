"""Opt-in, fail-closed dual-source validation gate for an existing paper feed.

Never calls order execution. Existing Coinbase feed and risk policy remain authoritative.
A research cross-check is *additional* evidence, not a replacement for executable books.
"""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Event, Lock, Thread

from alpha_lab.data.dual_source_check import MarketDataHalt, crosscheck

PRODUCT_ASSETS = {"BTC-USD": "BTC", "ETH-USD": "ETH", "SOL-USD": "SOL"}


class DualSourcePaperGate:
    """Feed-compatible wrapper; caller must explicitly refresh outside order path.

    On startup and on any refresh failure, all gated products are unhealthy.
    Evidence expires; a cached successful comparison cannot indefinitely authorise
    new simulated orders. Refreshing does not change the underlying feed.
    """

    def __init__(self, feed, *, validator=crosscheck, max_age_seconds=60):
        if not 0 < max_age_seconds <= 300:
            raise ValueError("invalid gate age")
        self.feed = feed
        self.validator = validator
        self.max_age_seconds = max_age_seconds
        self.lock = Lock()
        self.validated = {}
        self._refresh_generation = 0
        self._stop = Event()
        self._worker = None

    def refresh(self, *, now=None):
        now = datetime.now(timezone.utc) if now is None else now
        if now.utcoffset() is None or now.utcoffset().total_seconds() != 0:
            raise ValueError("UTC time required")
        stamp = int(now.timestamp())
        with self.lock:
            self._refresh_generation += 1
            generation = self._refresh_generation
            self.validated.clear()  # fail closed throughout refresh
        passed = {}
        for product, asset in PRODUCT_ASSETS.items():
            try:
                evidence = self.validator(asset, now=stamp)
                if (not isinstance(evidence, dict)
                        or evidence.get("status") != "VERIFIED_RESEARCH_DATA"
                        or evidence.get("asset") != asset
                        or evidence.get("observed_at_utc") != stamp):
                    raise MarketDataHalt("untrusted validation evidence")
                passed[product] = stamp
            except Exception:
                continue
        with self.lock:
            if generation != self._refresh_generation:
                return {}  # an older, slower refresh cannot overwrite newer evidence
            self.validated = passed
        return dict(passed)

    def snapshot(self, now):
        quotes, healthy, history = self.feed.snapshot(now)
        stamp = int(now.timestamp())
        with self.lock:
            passed = dict(self.validated)
        healthy = dict(healthy)
        for product in PRODUCT_ASSETS:
            age = stamp - passed.get(product, -10**12)
            healthy[product] = bool(healthy.get(product)) and 0 <= age <= self.max_age_seconds
        return quotes, healthy, history

    def poll(self, pool):
        return self.feed.poll(pool)

    def start(self, on_poll, **kwargs):
        if self._worker is not None:
            raise RuntimeError("dual-source polling already started")
        if not callable(on_poll):
            raise ValueError("health callback required")
        self.feed.start(on_poll, **kwargs)

        def run():
            while not self._stop.is_set():
                self.refresh()
                try:
                    on_poll()  # propagate new HALT state to the session immediately
                except Exception:
                    with self.lock:
                        self.validated.clear()
                self._stop.wait(30)

        self._worker = Thread(target=run, name="alpha-dual-source-check", daemon=True)
        self._worker.start()

    def close(self):
        self._stop.set()
        try:
            if self._worker is not None:
                self._worker.join(timeout=35)
                if self._worker.is_alive():
                    raise RuntimeError("dual-source worker still active: HALT")
        finally:
            self.feed.close()
