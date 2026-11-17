"""Bounded read-only Coinbase feed soak; no paper or live execution imports."""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from alpha_lab.research.coinbase_paper_book import PRODUCTS
from alpha_lab.research.paper_market_feed import PaperMarketFeed


def observe(*, duration_seconds=1800, interval_seconds=15, feed=None,
            clock=lambda: datetime.now(timezone.utc), monotonic=time.monotonic,
            sleep=time.sleep):
    if not 30 <= duration_seconds <= 7200 or not 2 <= interval_seconds <= 120:
        raise ValueError("bounded duration 30..7200 and interval 2..120 required")
    feed = feed if feed is not None else PaperMarketFeed()
    start = monotonic()
    deadline = start + duration_seconds
    counts = {p: {"healthy": 0, "unverified": 0, "max_exchange_age_seconds": 0.0}
              for p in PRODUCTS}
    samples = 0
    with ThreadPoolExecutor(max_workers=len(PRODUCTS)) as pool:
        while True:
            feed.poll(pool)
            now = clock()
            quotes, healthy, _ = feed.snapshot(now)
            samples += 1
            for product in PRODUCTS:
                bucket = counts[product]
                if healthy[product]:
                    bucket["healthy"] += 1
                    age = (now - quotes[product].exchange_at).total_seconds()
                    bucket["max_exchange_age_seconds"] = max(bucket["max_exchange_age_seconds"], age)
                else:
                    bucket["unverified"] += 1
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            sleep(min(interval_seconds, remaining))
    for product in PRODUCTS:
        counts[product]["availability_pct"] = round(100 * counts[product]["healthy"] / samples, 2)
    return {"mode": "READ_ONLY", "status": "PASS" if all(
        counts[p]["unverified"] == 0 for p in PRODUCTS) else "DEGRADED",
        "duration_requested_seconds": duration_seconds, "samples": samples,
        "products": counts, "paper_orders": 0, "live_orders": 0,
        "live_execution_authorised": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-seconds", type=int, default=1800)
    parser.add_argument("--interval-seconds", type=int, default=15)
    args = parser.parse_args()
    print(json.dumps(observe(duration_seconds=args.duration_seconds,
                             interval_seconds=args.interval_seconds), indent=2))


if __name__ == "__main__":
    main()
