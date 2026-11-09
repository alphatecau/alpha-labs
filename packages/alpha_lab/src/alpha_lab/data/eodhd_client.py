"""Research-only EODHD client boundary; injected transport, disabled by default.

Never logs or returns credentials. No default network transport is provided.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os
import re
from typing import Callable

from alpha_lab.data.eodhd_research import EODHDResearchError, parse_eodhd_eod

_ALLOWED_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,39}$")


@dataclass(frozen=True)
class ProviderReply:
    status: int
    body: str


def load_eodhd_research(
    symbol: str,
    start: date,
    end: date,
    *,
    api_token: str,
    transport: Callable[[str, dict[str, str]], ProviderReply],
    enabled: bool = False,
):
    """Request validated daily bars through a caller-provided, audited transport.

    Transport receives a fixed relative path and params. It must enforce TLS,
    trusted hostname, redaction, timeouts and no redirects before live use.
    No real transport is shipped or configured.
    """
    if not enabled or os.environ.get("ALPHA_EODHD_RESEARCH_ENABLED") != "true":
        raise EODHDResearchError("EODHD research client disabled")
    if not isinstance(symbol, str) or not _ALLOWED_SYMBOL.fullmatch(symbol):
        raise EODHDResearchError("Invalid symbol")
    if not isinstance(start, date) or not isinstance(end, date) or start > end:
        raise EODHDResearchError("Invalid date interval")
    if not isinstance(api_token, str) or not api_token or len(api_token) > 512:
        raise EODHDResearchError("Missing or invalid credential")
    if not callable(transport):
        raise EODHDResearchError("Explicit transport required")
    params = {"api_token": api_token, "from": start.isoformat(), "to": end.isoformat(), "fmt": "json"}
    try:
        reply = transport("/api/eod/" + symbol, params)
    except Exception:
        raise EODHDResearchError("Provider transport failure") from None
    if not isinstance(reply, ProviderReply):
        raise EODHDResearchError("Invalid provider response")
    if reply.status == 429:
        raise EODHDResearchError("Provider rate limited")
    if reply.status in (401, 403):
        raise EODHDResearchError("Provider access denied")
    if reply.status != 200:
        raise EODHDResearchError("Provider unavailable")
    if not isinstance(reply.body, str):
        raise EODHDResearchError("Invalid provider payload")
    bars, digest = parse_eodhd_eod(reply.body, enabled=True)
    if any(not (start <= bar.day <= end) for bar in bars):
        raise EODHDResearchError("Provider returned out-of-range dates")
    return bars, digest
