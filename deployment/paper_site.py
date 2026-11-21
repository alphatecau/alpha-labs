"""Read-only paper Site routes and shared, demand-driven public price observations."""
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from urllib.parse import parse_qs


PAPER_SITE = "https://alpha-labs-intelligence.alpha-tec-au86.chatgpt.site"


def callback_params(query):
    if len(query) > 4096:
        return {}
    try:
        return parse_qs(query, keep_blank_values=True, strict_parsing=True, max_num_fields=3)
    except ValueError:
        return {}


def page_number(query, paginated):
    if not query:
        return 0
    if paginated and re.fullmatch(r"page=(0|[1-9][0-9]{0,4})", query):
        return int(query[5:])
    raise ValueError("invalid paper query")


class RelayBudget:
    """Bound per-owner paper reads per worker, including on failure."""
    def __init__(self, *, clock=monotonic, limit=30):
        self.clock, self.limit = clock, limit
        self.lock = Lock()
        self.until = 0
        self.counts = {}

    def allow(self, owner):
        with self.lock:
            now = self.clock()
            if now >= self.until:
                self.counts.clear()
                self.until = now + 60
            count = self.counts.get(owner, 0)
            if count >= self.limit or (not count and len(self.counts) >= 2048):
                return False
            self.counts[owner] = count + 1
            return True


class MarketBooks:
    """Reuse the simulator's exchange validation and 429 backoff without a trading runtime."""
    def __init__(self, feed=None):
        from alpha_lab.research.paper_market_feed import PaperMarketFeed
        self.feed = feed or PaperMarketFeed()
        self.poll_lock = Lock()
        self.next_poll = 0

    def snapshot(self):
        if self.poll_lock.acquire(blocking=False):
            try:
                if monotonic() >= self.next_poll:
                    with ThreadPoolExecutor(max_workers=len(self.feed.product_retry_at)) as pool:
                        self.feed.poll(pool)
                    self.next_poll = monotonic() + 5
            finally:
                self.poll_lock.release()
        now = datetime.now(timezone.utc)
        quotes, healthy, history = self.feed.snapshot(now)
        return {"as_of": now.isoformat(), "history": history, "market": {
            symbol: {"bid": str(q.bid), "ask": str(q.ask), "source": q.source,
                     "healthy": healthy[symbol], "source_time": q.source_timestamp,
                     "age_seconds": round((now - q.exchange_at).total_seconds(), 2)}
            for symbol, q in quotes.items()}}


def research_evidence():
    from deployment.staging_probe import AUDIT, AUDIT_SHA256
    raw = AUDIT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != AUDIT_SHA256:
        raise ValueError("research evidence mismatch")
    audit = json.loads(raw)
    if audit["trading_enabled"] is not False:
        raise ValueError("unexpected research mode")
    markets = []
    for market in audit["markets"]:
        period = market["periods"]["test_unsealed"]
        markets.append({"symbol": market["symbol"], "start": period["start_utc"],
                        "end": period["end_exclusive_utc"], "return_pct": period["strategy_return_pct"]})
    return {"sha256": AUDIT_SHA256, "reviewed_at": audit["reviewed_at_utc"], "markets": markets}
