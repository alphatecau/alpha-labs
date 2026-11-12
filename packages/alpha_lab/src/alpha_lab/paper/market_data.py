"""Provider-neutral read-only acquisition; licences remain independently reviewed."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from .contracts import ContractError, Quote, timestamp, utc


@dataclass(frozen=True)
class Provenance:
    provider: str
    source_ref: str
    terms_ref: str
    licence_review_status: str = "UNVERIFIED"


class QuoteProvider(Protocol):
    provenance: Provenance
    async def latest(self, instrument: str) -> Quote: ...


class MarketDataUnavailable(RuntimeError):
    pass


class MarketDataGateway:
    """Bounded provider failover with identical causal validation on each path."""
    def __init__(self, providers: tuple[QuoteProvider, ...], *, timeout_seconds=2):
        if not providers or len(providers) > 3 or not 0 < timeout_seconds <= 10:
            raise ValueError("one to three providers and bounded timeout required")
        self.providers, self.timeout_seconds = providers, timeout_seconds

    async def latest(self, instrument: str, now: str) -> tuple[Quote, tuple[str, ...]]:
        incidents = []
        for provider in self.providers:
            try:
                q = await asyncio.wait_for(provider.latest(instrument), timeout=self.timeout_seconds)
                if not isinstance(q, Quote) or q.instrument != instrument:
                    raise ContractError("provider returned an incorrect instrument")
                q.check(now)
                return q, tuple(incidents)
            except (TimeoutError, OSError, ValueError):
                # Provider exceptions/content never become executable instructions.
                incidents.append(provider.provenance.provider+":unavailable_or_invalid")
        raise MarketDataUnavailable("all read-only quote providers failed validation")


def synthetic_quote(now: str, *, midpoint="100", source_ref="fixture-feed") -> Quote:
    """An explicit synthetic scenario; never fetches or imitates real market prices."""
    from decimal import Decimal
    from .contracts import number
    mid = number(midpoint, positive=True)
    decision = utc(now)
    return Quote(
        instrument="TEST/AUD", venue="synthetic", currency="AUD",
        event_time=timestamp(decision-timedelta(milliseconds=100)),
        received_time=timestamp(decision-timedelta(milliseconds=50)),
        bid=mid-Decimal("0.1"), ask=mid+Decimal("0.1"),
        bid_size=Decimal("100"), ask_size=Decimal("100"),
        source_ref=source_ref, synthetic=True)
