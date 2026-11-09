"""Read-only, fail-closed market valuation from validated observations.

This is a research boundary, not authenticated market ingestion or trade authority.
"""
from datetime import datetime, timezone
from alpha_lab.research.paper_market_provenance import validate_observation
from alpha_lab.research.paper_portfolio_valuation import derive_portfolio

def derive_verified_portfolio(ledger, observations, *, now=None, allowed_sources=()):
    if now is None:
        now=datetime.now(timezone.utc)
    if not isinstance(observations, dict):
        raise ValueError("HALT: market observations mapping required")
    required={symbol for symbol,qty in ledger.positions.items() if qty}
    if not required.issubset(observations):
        raise ValueError("HALT: missing portfolio market observations")
    marks={}
    for symbol in required:
        observed=validate_observation(observations[symbol],now=now,allowed_sources=allowed_sources)
        if observed.symbol != symbol:
            raise ValueError("HALT: mismatched market observation symbol")
        marks[symbol]=observed.mid
    return derive_portfolio(ledger,marks)
