"""Strict provenance boundary for research-only market observations.

This validates structure, timestamps and an allowlisted feed identity; it does
not authenticate the feed or establish independently trusted market prices.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from alpha_lab.research.paper_simulator import number

@dataclass(frozen=True)
class MarketObservation:
    symbol: str
    mid: Decimal
    timestamp: datetime
    source: str

def validate_observation(observation, *, now, allowed_sources=(), max_age_seconds=60):
    if not isinstance(observation, MarketObservation):
        raise ValueError("HALT: market observation required")
    if not isinstance(observation.symbol, str) or not observation.symbol or len(observation.symbol)>32:
        raise ValueError("HALT: invalid symbol")
    if not isinstance(observation.source, str) or not observation.source or observation.source not in allowed_sources:
        raise ValueError("HALT: unapproved market source")
    if not isinstance(now, datetime) or not isinstance(observation.timestamp, datetime):
        raise ValueError("HALT: UTC timestamp required")
    if now.tzinfo is None or observation.timestamp.tzinfo is None:
        raise ValueError("HALT: timezone required")
    if now.utcoffset()!=timedelta(0) or observation.timestamp.utcoffset()!=timedelta(0):
        raise ValueError("HALT: UTC timestamp required")
    age=now-observation.timestamp
    if not timedelta(0)<=age<=timedelta(seconds=max_age_seconds):
        raise ValueError("HALT: stale or future market observation")
    mid=number(observation.mid)
    if mid<=0:
        raise ValueError("HALT: non-positive market mid")
    return MarketObservation(observation.symbol,mid,observation.timestamp,observation.source)
