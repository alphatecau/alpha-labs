"""Deterministic US ETF quote rehearsal with no network or market-data claims."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from alpha_lab.research.live_paper_quotes import PaperQuote, verified_book
from alpha_lab.research.paper_market import PaperMarket

ETF_SYMBOLS = ("SPY", "QQQ", "IWM", "XLF", "XLE")
SOURCE = "SYNTHETIC_US_ETF_V1"
OPEN = datetime(2026, 11, 12, 14, 30, tzinfo=timezone.utc)
CLOSE = datetime(2026, 11, 12, 21, tzinfo=timezone.utc)


@dataclass(frozen=True)
class SessionCalendar:
    windows: tuple[tuple[datetime, datetime], ...]

    def __post_init__(self):
        previous_close = None
        if not self.windows:
            raise ValueError("explicit market sessions required")
        for opening, closing in self.windows:
            if (not all(isinstance(value, datetime) and value.utcoffset() == timedelta(0)
                        for value in (opening, closing)) or opening >= closing
                    or previous_close is not None and opening < previous_close):
                raise ValueError("invalid UTC market-session windows")
            previous_close = closing

    def covers(self, stamp, now):
        return any(opening <= stamp <= now < closing for opening, closing in self.windows)


CALENDAR = SessionCalendar(((OPEN, CLOSE),))


def _accepts(quote, now):
    return (verified_book(quote, now, source=SOURCE, products=ETF_SYMBOLS, max_age=timedelta(seconds=10))
            and CALENDAR.covers(quote.exchange_at, now))


ETF_FIXTURE_MARKET = PaperMarket("synthetic-us-etf-v1", ETF_SYMBOLS, _accepts, Decimal("1"))


class SyntheticEtfFeed:
    # Pre-open, three illustrative in-session updates, then the session close.
    scenarios = (
        (OPEN - timedelta(seconds=1), "100", "1"),
        (OPEN, "100", "1"),
        (OPEN + timedelta(seconds=1), "99.90", "1"),
        (OPEN + timedelta(seconds=2), "101", "10"),
        (CLOSE, "101", "10"),
    )

    def __init__(self):
        self.index = 0

    def clock(self):
        return self.scenarios[self.index][0]

    def resume_from(self, events):
        sequence = max((fill["details"]["source_sequence"] for fill in events), default=1)
        if not 1 <= sequence <= len(self.scenarios):
            raise ValueError("journal refers to an unsupported synthetic scenario")
        self.index = sequence - 1

    def advance(self):
        if self.index + 1 >= len(self.scenarios):
            raise ValueError("synthetic scenario finished")
        self.index += 1

    def snapshot(self, now):
        stamp, bid, depth = self.scenarios[self.index]
        quotes = {}
        for offset, symbol in enumerate(ETF_SYMBOLS):
            price = Decimal(bid) + offset * 10
            quotes[symbol] = PaperQuote(symbol, price, price + Decimal("0.02"), stamp, SOURCE,
                                      exchange_at=stamp, source_timestamp=stamp.isoformat(),
                                      source_sequence=self.index + 1, bid_size=Decimal(depth),
                                      ask_size=Decimal(depth))
        return quotes, {symbol: _accepts(quote, now) for symbol, quote in quotes.items()}, {}
