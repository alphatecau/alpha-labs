"""Timestamped Coinbase Exchange level-one books for paper simulation."""
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from alpha_lab.data.public_https import decode_public_json, read_public_https
from alpha_lab.research.live_paper_quotes import PaperQuote, verified_book

PRODUCTS = ("BTC-USD", "ETH-USD", "SOL-USD")
SOURCE = "Coinbase Exchange level 1"
BASE_URL = "https://api.exchange.coinbase.com"
MAX_AGE = timedelta(seconds=10)
HTTP_TIMEOUT_SECONDS = 8
_NUMBER = re.compile(r"[0-9]{1,10}(?:\.[0-9]{1,12})?")
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z")


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
    if received.utcoffset() != timedelta(0) or not timedelta(0) <= received - event <= MAX_AGE:
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
    payload = read_public_https(url, origin=BASE_URL, max_bytes=8192, timeout=HTTP_TIMEOUT_SECONDS,
                               content_types=("application/json",), opener=opener,
                               headers={"Cache-Control": "no-cache, no-store, max-age=0"})
    return parse_book(product, decode_public_json(payload), clock())


def executable(quote, now):
    return verified_book(quote, now, source=SOURCE, products=PRODUCTS, max_age=MAX_AGE)
