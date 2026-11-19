"""Validate independently retained audit checkpoint metadata (offline)."""
import re


class CheckpointDenied(ValueError):
    """Checkpoint evidence cannot be trusted."""


def verify_checkpoint_metadata(checkpoint, expected_audience):
    required = {"audience", "sequence", "head_hash", "receipt_sha256", "storage_domain"}
    if not isinstance(checkpoint, dict) or set(checkpoint) != required:
        raise CheckpointDenied("invalid checkpoint fields")
    if checkpoint["audience"] != expected_audience:
        raise CheckpointDenied("checkpoint audience mismatch")
    if type(checkpoint["sequence"]) is not int or checkpoint["sequence"] < 0:
        raise CheckpointDenied("invalid sequence")
    for key in ("head_hash", "receipt_sha256"):
        value = checkpoint[key]
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise CheckpointDenied("invalid checkpoint hash")
    if checkpoint["storage_domain"] not in ("independent-auditor-drive", "offline-auditor"):
        raise CheckpointDenied("untrusted storage domain")
    return True
