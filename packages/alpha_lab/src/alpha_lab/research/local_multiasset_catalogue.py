"""Local multi-asset paper-trading instrument catalogue; no broker access.

Listing an instrument does not assert live feed support, price quality, market
hours, execution feasibility, borrow availability, or permission to place orders.
Unknown instruments must be explicitly registered with an independently
validated market-data adapter before simulated orders can be enabled.
"""
from dataclasses import dataclass
import re

_ALLOWED_ASSETS = {"crypto", "equity", "etf", "index", "forex"}
_ALLOWED_VENUES = {"CRYPTO", "NASDAQ", "NYSE", "AMEX", "ASX", "LSE", "TSX", "XETRA", "TSE", "FX"}
_SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9.\-]{0,19}\Z")


@dataclass(frozen=True)
class Instrument:
    symbol: str
    venue: str
    asset_class: str
    quote_currency: str
    description: str = ""
    data_status: str = "UNVERIFIED"
    order_status: str = "DISABLED"

    def __post_init__(self):
        if (not _SYMBOL.fullmatch(self.symbol)
                or self.venue not in _ALLOWED_VENUES
                or self.asset_class not in _ALLOWED_ASSETS
                or not re.fullmatch(r"[A-Z]{3,5}", self.quote_currency)
                or self.data_status != "UNVERIFIED"
                or self.order_status != "DISABLED"):
            raise ValueError("invalid or prematurely enabled instrument")


def catalogue():
    """Broad discoverability; every entry defaults to NO DATA / NO ORDERS."""
    rows = []
    for symbol in ("BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "AVAX",
                   "LINK", "DOT", "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM",
                   "HBAR", "NEAR", "ETC", "FIL", "APT", "ARB", "OP", "SUI",
                   "TRX", "PEPE", "SHIB"):
        rows.append(Instrument(symbol, "CRYPTO", "crypto", "USD"))
    for symbol in ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
                   "AMD", "INTC", "NFLX", "JPM", "BAC", "V", "MA", "KO",
                   "WMT", "COST", "PLTR", "COIN", "MSTR"):
        rows.append(Instrument(symbol, "NASDAQ" if symbol in
                               {"AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
                                "AMD", "INTC", "NFLX", "COST", "PLTR", "MSTR"} else "NYSE",
                               "equity", "USD"))
    for symbol in ("SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "XLF", "XLE",
                   "XLK", "GLD", "SLV", "TLT", "ARKK"):
        rows.append(Instrument(symbol, "AMEX", "etf", "USD"))
    for symbol in ("BHP", "CBA", "CSL", "WBC", "NAB", "ANZ", "WES", "WOW",
                   "MQG", "RIO", "FMG", "TLS", "XRO", "REA", "ALL", "VAS", "A200", "VGS"):
        rows.append(Instrument(symbol, "ASX",
                               "etf" if symbol in {"VAS", "A200", "VGS"} else "equity",
                               "AUD"))
    return tuple(rows)


def lookup(symbol, venue=None):
    if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
        raise ValueError("invalid instrument symbol")
    found = [x for x in catalogue() if x.symbol == symbol and
             (venue is None or x.venue == venue)]
    if len(found) != 1:
        raise LookupError("instrument unknown or ambiguous; no orders permitted")
    return found[0]


def eligible_for_order(instrument, *, quote_verified=False, session_open=False,
                       risk_approved=False, durable_journal=False):
    """A catalogue entry alone can never unlock an order."""
    return (instrument.order_status == "PAPER_ENABLED" and
            instrument.data_status == "VERIFIED" and
            quote_verified is True and session_open is True and
            risk_approved is True and durable_journal is True)
