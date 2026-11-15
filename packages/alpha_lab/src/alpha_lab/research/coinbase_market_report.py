"""Read-only Coinbase top-of-book market report. No account or execution access."""
from datetime import datetime, timezone
from decimal import Decimal

from alpha_lab.research.coinbase_paper_book import PRODUCTS, executable, fetch_book


def market_report(*, fetch=fetch_book, clock=lambda: datetime.now(timezone.utc)):
    """Return per-symbol observations; failures are UNVERIFIED, never cached as live."""
    rows = []
    for product in PRODUCTS:
        try:
            quote = fetch(product)
            now = clock()
            if not executable(quote, now):
                raise ValueError("quote failed freshness or integrity verification")
            spread = (quote.ask - quote.bid) / quote.mid * Decimal("10000")
            rows.append({
                "symbol": product, "status": "VERIFIED", "source": quote.source,
                "bid_usd": str(quote.bid), "ask_usd": str(quote.ask),
                "mid_usd": str(quote.mid), "spread_bps": str(spread),
                "exchange_at": quote.exchange_at.isoformat(),
                "observed_at": quote.observed_at.isoformat(),
                "checked_at": now.isoformat(),
                "age_seconds": (now - quote.exchange_at).total_seconds(),
                "source_sequence": quote.source_sequence,
            })
        except (ValueError, OSError, TimeoutError) as exc:
            rows.append({"symbol": product, "status": "UNVERIFIED",
                         "reason": type(exc).__name__, "bid_usd": None,
                         "ask_usd": None, "mid_usd": None})
    return {"mode": "READ_ONLY_RESEARCH", "currency": "USD",
            "simulated_only": True, "live_execution_authorised": False,
            "markets": rows}


def main():
    import json
    print(json.dumps(market_report(), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
