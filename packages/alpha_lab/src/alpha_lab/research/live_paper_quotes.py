"""Public market-data adapter for offline-only paper simulation.

No account API, authenticated exchange endpoints, order submission or scheduler.
The adapter returns verified quotes; it never invokes PaperRuntime.execute.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from urllib.parse import urlencode
from alpha_lab.data.public_https import decode_public_json, read_public_https
from alpha_lab.research.paper_simulator import number

ORIGIN = "https://data-api.binance.vision"
SYMBOLS = frozenset(("BTCUSDT", "ETHUSDT", "SOLUSDT"))

@dataclass(frozen=True)
class PaperQuote:
    symbol: str
    bid: Decimal
    ask: Decimal
    observed_at: datetime
    source: str = "binance-public-bookTicker"
    simulated_only: bool = True
    exchange_at: datetime | None = None
    source_timestamp: str | None = None
    source_sequence: int | None = None
    bid_size: Decimal | None = None
    ask_size: Decimal | None = None

    @property
    def mid(self):
        return (self.bid + self.ask) / 2

def parse_book_ticker(payload, *, symbol, observed_at):
    if symbol not in SYMBOLS:
        raise ValueError("unsupported symbol")
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None or observed_at.utcoffset() != timedelta(0):
        raise ValueError("UTC observation time required")
    if not isinstance(payload, dict) or payload.get("symbol") != symbol:
        raise ValueError("quote symbol mismatch")
    bid, ask = number(payload.get("bidPrice")), number(payload.get("askPrice"))
    if bid <= 0 or ask <= 0 or bid > ask:
        raise ValueError("invalid or crossed quote")
    return PaperQuote(symbol, bid, ask, observed_at)

def fetch_public_quote(symbol, *, opener=None, clock=lambda: datetime.now(timezone.utc)):
    """GET-only public market data. Response time is NOT exchange event time."""
    if symbol not in SYMBOLS:
        raise ValueError("unsupported symbol")
    url = ORIGIN + "/api/v3/ticker/bookTicker?" + urlencode({"symbol": symbol})
    raw = read_public_https(url, origin=ORIGIN, max_bytes=8192, timeout=5,
                            content_types=("application/json",), opener=opener)
    payload = decode_public_json(raw)
    return parse_book_ticker(payload, symbol=symbol, observed_at=clock())

def quote_is_fresh(quote, *, now, max_age_seconds=10):
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timedelta(0):
        return False
    age = (now - quote.observed_at).total_seconds()
    return 0 <= age <= max_age_seconds


def verified_book(quote, now, *, source, products, max_age, max_future=timedelta(0)):
    if (not isinstance(quote, PaperQuote) or quote.symbol not in products or quote.source != source
            or quote.simulated_only is not True or type(quote.source_sequence) is not int
            or not 0 < quote.source_sequence < 2**63):
        return False
    stamps = (now, quote.exchange_at, quote.observed_at)
    if (not all(isinstance(t, datetime) and t.utcoffset() == timedelta(0) for t in stamps)
            or not isinstance(quote.source_timestamp, str) or len(quote.source_timestamp) > 40
            or not -max_future <= now - quote.exchange_at <= max_age
            or not timedelta(0) <= now - quote.observed_at <= max_age
            or quote.exchange_at > quote.observed_at + max_future):
        return False
    try:
        if datetime.fromisoformat(quote.source_timestamp) != quote.exchange_at:
            return False
    except ValueError:
        return False
    prices = (quote.bid, quote.ask, quote.bid_size, quote.ask_size)
    return (all(isinstance(value, Decimal) and value.is_finite() and value > 0 for value in prices)
            and quote.bid <= quote.ask and quote.ask - quote.bid <= quote.bid * Decimal("0.01"))

def simulated_fill_estimate(quote, *, side, quantity, fee_rate="0.001", slippage_bps="5"):
    """Cost estimate only; does not execute or mutate the paper ledger."""
    q, fee_pct, bps = map(number, (quantity, fee_rate, slippage_bps))
    if side not in ("BUY", "SELL") or q <= 0 or fee_pct < 0 or bps < 0:
        raise ValueError("invalid simulation parameters")
    reference = quote.ask if side == "BUY" else quote.bid
    execution = reference * (1 + bps / 10000 if side == "BUY" else 1 - bps / 10000)
    if execution <= 0:
        raise ValueError("invalid simulated execution")
    return {"mode": "SIMULATION_ONLY", "symbol": quote.symbol, "side": side,
            "quantity": str(q), "reference_mid": str(quote.mid),
            "executed_price": str(execution), "fee": str(q * execution * fee_pct),
            "source": quote.source, "observed_at": quote.observed_at.isoformat(),
            "simulated_only": True, "live_execution_authorised": False}
