"""Deterministic, read-only research review; does not modify strategies."""
from dataclasses import dataclass

@dataclass(frozen=True)
class DailyReview:
    verdict: str
    findings: tuple
    events_reviewed: int

def review_events(events):
    """Events require explicit type and status; malformed records fail closed."""
    findings = []
    count = 0
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get("type"), str) or not isinstance(event.get("status"), str):
            return DailyReview("HALT_REVIEW", ("malformed event",), count)
        count += 1
        if event["status"] in {"failed", "stale", "missing", "rejected"}:
            findings.append(f'{event["type"]}: {event["status"]}')
    if not count:
        return DailyReview("INSUFFICIENT_DATA", ("no events supplied",), 0)
    return DailyReview("REVIEW_REQUIRED" if findings else "NO_FLAGS", tuple(findings), count)
