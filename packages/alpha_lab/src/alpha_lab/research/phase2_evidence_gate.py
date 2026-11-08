"""Conservative evidence-gate integration for historical archive data.

No evidence supplied by the caller is independently authenticated here.
The output is never an authorisation to promote strategies or execute trades.
"""
from __future__ import annotations

from alpha_lab.research.phase1_archival_pit import verify_archival_availability
from alpha_lab.research.phase2_archive_provenance import verify_archive_provenance


def evaluate_archived_research_evidence(*, availability, provenance):
    """Combine chronological checks and actual signed-byte integrity checks.

    availability: keyword arguments for verify_archival_availability.
    provenance: keyword arguments for verify_archive_provenance.
    Reject inconsistent identities, decision times and content hashes.
    """
    if not isinstance(availability, dict) or not isinstance(provenance, dict):
        raise ValueError("Both archival availability and provenance inputs required")
    chronological = verify_archival_availability(**availability)
    verified = verify_archive_provenance(**provenance)
    if availability["decision_time"] != provenance["decision_time"]:
        raise ValueError("Decision time mismatch between evidence records")
    if chronological["archive_record_id"] != verified["archive_id"]:
        raise ValueError("Archive record identity mismatch")
    if chronological["archive_sha256"] != verified["sha256"]:
        raise ValueError("Archived byte digest mismatch")
    if chronological["archive_provider"] != provenance["provider_id"]:
        raise ValueError("Archive provider identity mismatch")
    return {
        "status": "EVIDENCE_CONSISTENT_PROVENANCE_UNVERIFIED",
        "archive_id": verified["archive_id"],
        "archive_sha256": verified["sha256"],
        "chronology_consistent": True,
        "signed_bytes_consistent": True,
        "provider_identity_independently_authenticated": False,
        "historical_capture_independently_attested": False,
        "eligible_for_strategy_promotion": False,
        "eligible_for_live_trading": False,
        "next_gate": "INDEPENDENT_ARCHIVE_IDENTITY_AND_TIMESTAMP_ATTESTATION",
    }
