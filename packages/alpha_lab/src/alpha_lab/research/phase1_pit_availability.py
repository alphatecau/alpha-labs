"""Fail-closed point-in-time availability gate for externally supplied evidence.

A retrieval timestamp alone is not proof of when information was first public.
Requires both externally documented publication time and actual acquisition time.
"""
from __future__ import annotations
from datetime import datetime, timezone


def verify_evidence_available(*, decision_time, publication_time, retrieved_time,
                              source_id, immutable_sha256, required_lag_seconds=0):
    stamps = (decision_time, publication_time, retrieved_time)
    if any(not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None for t in stamps):
        raise ValueError("Timezone-aware evidence timestamps required")
    if not isinstance(required_lag_seconds, int) or isinstance(required_lag_seconds, bool) or required_lag_seconds < 0:
        raise ValueError("Invalid publication lag")
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("Missing evidence source")
    if not isinstance(immutable_sha256, str) or len(immutable_sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in immutable_sha256):
        raise ValueError("Missing immutable evidence hash")
    decision, published, retrieved = (t.astimezone(timezone.utc) for t in stamps)
    from datetime import timedelta
    if published + timedelta(seconds=required_lag_seconds) > decision:
        raise ValueError("Evidence published after decision availability cut-off")
    if retrieved > decision:
        raise ValueError("Evidence acquired after decision; historical availability not independently established")
    if published > retrieved:
        raise ValueError("Evidence acquisition precedes documented publication")
    return {
        "status": "TIMESTAMPS_CONSISTENT_SOURCE_NOT_AUTHENTICATED",
        "source_id": source_id,
        "sha256": immutable_sha256.lower(),
        "available_for_decision_by_supplied_timestamps": True,
        "publication_independently_authenticated": False,
        "eligible_for_strategy_promotion": False,
    }
