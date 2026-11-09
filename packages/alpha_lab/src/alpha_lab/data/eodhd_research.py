"""Disabled-by-default, offline-parse-only EODHD research boundary.

No HTTP, MCP, broker or credential handling is implemented here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os


class EODHDResearchError(ValueError):
    """Reject invalid or unauthorised research data."""


@dataclass(frozen=True)
class EODHDBar:
    day: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


def parse_eodhd_eod(payload: str, *, enabled: bool = False) -> tuple[tuple[EODHDBar, ...], str]:
    """Validate an immutable EODHD EOD JSON fixture; never fetch data.

    Returns sorted bars and SHA-256 of the exact source bytes. Neither
    integrity hashing nor parsing authenticates the provider.
    """
    if not enabled or os.environ.get("ALPHA_EODHD_RESEARCH_ENABLED") != "true":
        raise EODHDResearchError("EODHD research adapter disabled")
    if len(payload.encode("utf-8")) > 2_000_000:
        raise EODHDResearchError("Payload exceeds research limit")
    try:
        records = json.loads(payload)
    except (ValueError, TypeError) as exc:
        raise EODHDResearchError("Invalid JSON") from exc
    if not isinstance(records, list) or not records:
        raise EODHDResearchError("Expected non-empty EOD bar list")
    if len(records) > 10000:
        raise EODHDResearchError("Too many bars")
    bars = []
    previous = None
    for record in records:
        if not isinstance(record, dict):
            raise EODHDResearchError("Invalid bar")
        try:
            day = date.fromisoformat(record["date"])
            values = [Decimal(str(record[k])) for k in ("open", "high", "low", "close", "volume")]
        except (KeyError, ValueError, TypeError, InvalidOperation) as exc:
            raise EODHDResearchError("Invalid EOD bar fields") from exc
        o, h, l, c, v = values
        if not all(x.is_finite() for x in values) or min(o, h, l, c) <= 0 or v < 0:
            raise EODHDResearchError("Non-finite or negative price/volume")
        if h < max(o, c, l) or l > min(o, c, h):
            raise EODHDResearchError("OHLC invariant violation")
        if previous is not None and day <= previous:
            raise EODHDResearchError("Dates must be unique and strictly increasing")
        previous = day
        bars.append(EODHDBar(day, o, h, l, c, v))
    return tuple(bars), hashlib.sha256(payload.encode("utf-8")).hexdigest()
