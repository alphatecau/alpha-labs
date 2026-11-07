"""Bounded event-driven synthetic sessions; no strategy changes or live scheduling."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .committee import FIXTURE_STRATEGY
from .contracts import Proposal, Quote, timestamp


@dataclass(frozen=True)
class SimulationEvent:
    event_id: str
    decision_time: str
    quote: Quote
    direction: str = "LONG"


async def run_session(engine, principal, account_id: str, events, *,
                      max_events=100, event_timeout_seconds=5):
    """Consume an async event stream; fail closed on timeout or provider failure.

    The caller must explicitly enable an isolated simulation account. Each event
    has a durable idempotency key. HALT ends the session and never auto-recovers.
    """
    if type(max_events) is not int or not 1 <= max_events <= 1000:
        raise ValueError("invalid event budget")
    if not 0 < event_timeout_seconds <= 30:
        raise ValueError("invalid event timeout")
    results = []
    iterator = events.__aiter__()
    try:
        for _ in range(max_events):
            try:
                event = await asyncio.wait_for(anext(iterator), timeout=event_timeout_seconds)
            except StopAsyncIteration:
                break
            if not isinstance(event, SimulationEvent):
                raise ValueError("invalid simulation event")
            if engine.store.snapshot(principal, account_id)["account"]["halted"]:
                break
            proposal = Proposal(account_id, event.quote.instrument, FIXTURE_STRATEGY,
                                event.direction, "2", "98", event.event_id)
            result = engine.autonomous_cycle(principal, proposal, event.quote, event.decision_time)
            results.append(result)
        return results
    except (TimeoutError, OSError, ValueError, asyncio.CancelledError):
        engine.control(principal, account_id, "halt", timestamp())
        raise
