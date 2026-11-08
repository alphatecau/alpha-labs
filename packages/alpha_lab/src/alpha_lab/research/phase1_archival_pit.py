"""Fail-closed historical evidence availability without invented retrieval timestamps.

Separates a modern research download from independently archived publication
evidence. An archive snapshot must itself be captured no later than the
historical trading decision; retrospective web pages do not suffice.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta


def _utc(value, name):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name + " must be timezone-aware")
    return value.astimezone(timezone.utc)


def verify_archival_availability(*, decision_time, publication_time,
                                 archive_capture_time, research_download_time,
                                 source_id, content_sha256, archived_content_sha256,
                                 archive_provider, archive_record_id,
                                 publication_lag_seconds=0):
    """Validate supplied archive chronology and exact content equality.

    Archive identity, capture timestamps and original publication assertions
    are not independently authenticated here. Never set an artificial old
    retrieval timestamp for a newly downloaded file.
    """
    decision = _utc(decision_time, "decision_time")
    published = _utc(publication_time, "publication_time")
    captured = _utc(archive_capture_time, "archive_capture_time")
    downloaded = _utc(research_download_time, "research_download_time")
    if not isinstance(publication_lag_seconds, int) or isinstance(publication_lag_seconds, bool) or publication_lag_seconds < 0:
        raise ValueError("Invalid publication lag")
    for name, value in (("source_id", source_id), ("archive_provider", archive_provider),
                        ("archive_record_id", archive_record_id)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Missing " + name)
    for value in (content_sha256, archived_content_sha256):
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value):
            raise ValueError("Invalid content hash")
    if content_sha256.lower() != archived_content_sha256.lower():
        raise ValueError("Archived content differs from research content")
    if published > captured:
        raise ValueError("Archive capture precedes original publication")
    if captured > decision:
        raise ValueError("Archive captured after historical decision")
    if published + timedelta(seconds=publication_lag_seconds) > decision:
        raise ValueError("Publication lag extends beyond decision")
    if downloaded < captured:
        raise ValueError("Research download predates archive capture")
    return {
        "status": "ARCHIVE_CHRONOLOGY_CONSISTENT_NOT_AUTHENTICATED",
        "source_id": source_id,
        "archive_record_id": archive_record_id,
        "archive_provider": archive_provider,
        "archive_sha256": archived_content_sha256.lower(),
        "research_download_after_decision_permitted": downloaded > decision,
        "archive_identity_independently_authenticated": False,
        "historical_availability_independently_proven": False,
        "eligible_for_strategy_promotion": False,
    }
