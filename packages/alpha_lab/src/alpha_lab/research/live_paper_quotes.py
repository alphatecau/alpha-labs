"""Public market-data adapter for offline-only paper simulation.

No account API, authenticated exchange endpoints, order submission or scheduler.
The adapter returns verified quotes; it never invokes PaperRuntime.execute.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
from urllib.parse import urlencode
from urllib.request import urlopen
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

def fetch_public_quote(symbol, *, opener=urlopen, clock=lambda: datetime.now(timezone.utc)):
    """GET-only public market data. Response time is NOT exchange event time."""
    if symbol not in SYMBOLS:
        raise ValueError("unsupported symbol")
    url = ORIGIN + "/api/v3/ticker/bookTicker?" + urlencode({"symbol": symbol})
    with opener(url, timeout=5) as response:
        if getattr(response, "status", 200) != 200:
            raise ValueError("market data unavailable")
        payload = json.load(response)
    return parse_book_ticker(payload, symbol=symbol, observed_at=clock())

def quote_is_fresh(quote, *, now, max_age_seconds=10):
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timedelta(0):
        return False
    age = (now - quote.observed_at).total_seconds()
    return 0 <= age <= max_age_seconds

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
