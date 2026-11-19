"""Fail-closed recovery for a signed checkpoint interrupted before latest CAS.

Recovery requires an explicit candidate object key; it NEVER scans and
automatically promotes arbitrary orphans. Caller must independently verify
database ancestry before using this helper for production.
"""
import hashlib
import json

from tools.level3_staging.anchor_continuity import verify_continuity
from tools.level3_staging.external_anchor import verify_anchor


class RecoveryDenied(ValueError):
    pass


def inspect_candidate(local_store, drive, key, audience, public_key):
    """Read-only: verify candidate signatures and both exact durable copies."""
    try:
        raw = local_store.read(key)
        remote = drive.read(key)
    except (OSError, KeyError, ValueError) as exc:
        raise RecoveryDenied("checkpoint evidence unavailable") from exc
    if not isinstance(raw, bytes) or remote != raw:
        raise RecoveryDenied("local and remote evidence differ")
    try:
        signed = json.loads(raw)
        receipt = signed["receipt"]
        verify_anchor(signed, public_key, audience, receipt)
        canonical = json.dumps(signed, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        if canonical != raw:
            raise RecoveryDenied("noncanonical signed evidence")
        digest = hashlib.sha256(raw).hexdigest()
        expected = (f"level3-checkpoints/{audience.replace(':', '_')}/"
                    f"{receipt['last_sequence']:020d}-{digest}.json")
        if expected != key:
            raise RecoveryDenied("candidate object key mismatch")
    except (TypeError, KeyError, AttributeError, json.JSONDecodeError) as exc:
        raise RecoveryDenied("malformed checkpoint") from exc
    return signed


def inspect_recovery(local_store, drive, key, audience, public_key):
    """Report candidate state; never change the trusted latest pointer."""
    candidate = inspect_candidate(local_store, drive, key, audience, public_key)
    latest = local_store.read_latest(audience)
    if latest is None:
        state = "unanchored_candidate_manual_review"
    else:
        if not isinstance(latest, dict) or not isinstance(latest.get("receipt"), dict):
            raise RecoveryDenied("invalid trusted latest checkpoint")
        verify_anchor(latest, public_key, audience, latest["receipt"])
        if latest == candidate:
            state = "already_committed"
        else:
            verdict = verify_continuity(latest["receipt"], candidate["receipt"])
            state = ("candidate_requires_database_ancestry_review"
                     if verdict == "requires_chain_verification"
                     else "candidate_requires_manual_review")
    return {"state": state, "receipt": candidate["receipt"], "promoted": False}
