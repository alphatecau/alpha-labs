"""Opt-in public Coinbase smoke and isolated paper execution, separate from offline CI."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from urllib.error import HTTPError

from alpha_lab.research.coinbase_paper_book import BookClockError, PRODUCTS, fetch_book
from alpha_lab.research.live_paper_session import LivePaperSession, PaperRejection
from alpha_lab.research.local_paper_terminal import DEFAULT_ACCOUNT
from alpha_lab.research.paper_market_feed import PaperMarketFeed


def smoke():
    quotes_evidence = {}

    def observe(symbol):
        start = monotonic()
        outcome = {}
        try:
            quote = fetch_book(symbol)
            outcome.update(status="PASS", source=quote.source, source_time=quote.source_timestamp,
                           receipt_time=quote.observed_at.isoformat(), sequence=quote.source_sequence,
                           age_seconds=(quote.observed_at - quote.exchange_at).total_seconds())
            return quote
        except BookClockError as exc:
            outcome.update(status="FAIL", reason="FUTURE_BOOK" if exc.age_seconds < 0 else "STALE_BOOK",
                           source_time=exc.source_time, receipt_time=exc.observed_at.isoformat(),
                           age_seconds=exc.age_seconds)
            raise
        except HTTPError as exc:
            outcome.update(status="FAIL", reason=f"HTTP_{exc.code}")
            raise
        except (OSError, ValueError) as exc:
            outcome.update(status="FAIL", reason=type(exc).__name__)
            raise
        finally:
            quotes_evidence[symbol] = {**outcome, "request_seconds": round(monotonic() - start, 4)}

    feed = PaperMarketFeed(fetch=observe)
    with ThreadPoolExecutor(len(PRODUCTS)) as pool:
        feed.poll(pool)
    now = datetime.now(timezone.utc)
    quotes, healthy, _ = feed.snapshot(now)
    evidence = {"quotes": quotes_evidence, "simulated_execution": "NOT TESTED"}
    if not all(healthy.values()):
        return evidence, 1
    lead = max((quote.exchange_at - now).total_seconds() for quote in quotes.values())
    if lead > 0:
        sleep(lead)
    try:
        with TemporaryDirectory(prefix="alpha-public-paper-smoke-") as directory:
            paper = LivePaperSession(directory, DEFAULT_ACCOUNT, feed)
            try:
                paper.control("arm", expected_revision=paper.state()["risk"]["revision"])
                for symbol, quote in quotes.items():
                    quantity = min(Decimal("5") / quote.ask, quote.bid_size, quote.ask_size).quantize(
                        paper.market.quantity_step, rounding=ROUND_DOWN)
                    stop = (quote.bid * Decimal("0.98")).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
                    for side in ("BUY", "SELL"):
                        order = {"order_id": f"public_smoke_{symbol}_{side}", "symbol": symbol, "side": side,
                                 "quantity": format(quantity, "f")}
                        if side == "BUY":
                            order["stop_price"] = str(stop)
                        fill = paper.order(order)["fill"]
                        if fill["simulated"] is not True:
                            raise ValueError("non-simulated ledger result")
                if any(paper.runtime.ledger.positions.values()):
                    raise ValueError("paper round trips did not close")
            finally:
                paper.close()
            recovered = LivePaperSession(directory, DEFAULT_ACCOUNT, feed, migrate=False)
            try:
                if not recovered.runtime.ledger.halted or recovered.runtime.ledger.sequence != 6:
                    raise ValueError("paper recovery did not return six fills and startup HALT")
                evidence.update(simulated_execution="PASS", fills=6, startup_halt=True,
                                cash_usd=str(recovered.runtime.ledger.cash))
            finally:
                recovered.close()
    except (OSError, ValueError, PaperRejection) as exc:
        evidence.update(simulated_execution="FAIL", reason=str(exc))
        return evidence, 1
    return evidence, 0


if __name__ == "__main__":
    result, code = smoke()
    print(json.dumps(result, indent=2))
    raise SystemExit(code)
