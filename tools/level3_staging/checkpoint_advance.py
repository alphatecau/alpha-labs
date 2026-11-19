"""Fail-closed offline continuity checks for independently retained audit checkpoints.

Metadata validation does not authenticate the checkpoint signer or storage.
"""
from tools.level3_staging.audit_checkpoint_policy import (
    CheckpointDenied,
    verify_checkpoint_metadata,
)


def verify_checkpoint_advance(previous, candidate, expected_audience):
    """Require a strictly increasing checkpoint sequence and a distinct chain head.

    The caller must independently authenticate both checkpoint records.
    """
    verify_checkpoint_metadata(previous, expected_audience)
    verify_checkpoint_metadata(candidate, expected_audience)
    if candidate["sequence"] <= previous["sequence"]:
        raise CheckpointDenied("checkpoint sequence must advance")
    if candidate["head_hash"] == previous["head_hash"]:
        raise CheckpointDenied("checkpoint head must advance")
    if candidate["storage_domain"] != previous["storage_domain"]:
        raise CheckpointDenied("checkpoint storage domain changed")
    return True
