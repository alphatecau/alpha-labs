"""Conservative promotion authority: never infer approval from report fields."""
from __future__ import annotations


def decide_strategy_promotion(*, assessment, archive_evidence=None):
    """Fail closed on absent or unverified historical provenance.

    This release intentionally provides no automatic promotion path. No
    caller-supplied boolean, status or claimed archive attestation may
    override the research-only decision.
    """
    if not isinstance(assessment, dict):
        raise ValueError("Assessment report required")
    if archive_evidence is not None and not isinstance(archive_evidence, dict):
        raise ValueError("Archive evidence must be a mapping")
    return {
        "status": "REJECTED_RESEARCH_ONLY",
        "promotion_authorised": False,
        "live_trading_authorised": False,
        "archive_provenance_independently_authenticated": False,
        "reason": "Independent archive identity, capture and complete promotion evidence not established",
    }
