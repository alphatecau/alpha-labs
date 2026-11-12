"""Timestamped Coinbase Exchange level-one books for paper simulation."""
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.request import HTTPRedirectHandler, Request, build_opener

from alpha_lab.research.live_paper_quotes import PaperQuote

PRODUCTS = ("BTC-USD", "ETH-USD", "SOL-USD")
SOURCE = "Coinbase Exchange level 1"
BASE_URL = "https://api.exchange.coinbase.com"
MAX_AGE = timedelta(seconds=10)
# Maximum accepted exchange-clock lead, based on observed Android clock skew.
MAX_FUTURE_SKEW = timedelta(milliseconds=500)
HTTP_TIMEOUT_SECONDS = 8
_NUMBER = re.compile(r"[0-9]{1,10}(?:\.[0-9]{1,12})?")
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def parse_book(product, body, received):
    if product not in PRODUCTS or not isinstance(body, dict) or body.get("auction_mode") is not False:
        raise ValueError("unsupported or indicative order book")
    timestamp = body.get("time")
    sequence = body.get("sequence")
    if not isinstance(timestamp, str) or not _TIMESTAMP.fullmatch(timestamp):
        raise ValueError("missing exchange book timestamp")
    if type(sequence) is not int or not 0 < sequence < 2**63:
        raise ValueError("invalid exchange book sequence")
    event = datetime.fromisoformat(timestamp)
    if received.utcoffset() != timedelta(0) or not -MAX_FUTURE_SKEW <= received - event <= MAX_AGE:
        raise ValueError("stale or future exchange book")

    def level(side):
        rows = body.get(side)
        if (not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], list)
                or len(rows[0]) != 3 or type(rows[0][2]) is not int or rows[0][2] <= 0):
            raise ValueError("invalid level-one depth")
        price, size = rows[0][:2]
        if not all(isinstance(value, str) and _NUMBER.fullmatch(value) for value in (price, size)):
            raise ValueError("invalid quote decimal")
        price, size = Decimal(price), Decimal(size)
        if min(price, size) <= 0:
            raise ValueError("empty price or depth")
        return price, size

    bid, bid_size = level("bids")
    ask, ask_size = level("asks")
    if bid > ask or (ask - bid) / bid > Decimal("0.01"):
        raise ValueError("crossed or unusually wide quote")
    return PaperQuote(product, bid, ask, received, SOURCE, exchange_at=event,
                      source_timestamp=timestamp, source_sequence=sequence,
                      bid_size=bid_size, ask_size=ask_size)


def fetch_book(product, *, clock=lambda: datetime.now(timezone.utc), opener=None):
    if product not in PRODUCTS:
        raise ValueError("unsupported product")
    url = f"{BASE_URL}/products/{product}/book?level=1"
    request = Request(url, headers={
        "Accept": "application/json", "Cache-Control": "no-cache, no-store, max-age=0",
        "User-Agent": "AlphaLabsPaperResearch/1.0",
    }, method="GET")
    request_open = opener or build_opener(NoRedirect()).open
    with request_open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("unexpected provider response")
        payload = response.read(8193)
    if len(payload) > 8192:
        raise ValueError("provider response exceeds limit")
    return parse_book(product, json.loads(payload), clock())


def executable(quote, now):
    return (quote.source == SOURCE and quote.simulated_only is True
            and quote.exchange_at is not None
            and -MAX_FUTURE_SKEW <= now - quote.exchange_at <= MAX_AGE
            and timedelta(0) <= now - quote.observed_at <= MAX_AGE)
