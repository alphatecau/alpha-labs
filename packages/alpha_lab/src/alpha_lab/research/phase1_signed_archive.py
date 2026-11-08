"""File-byte integrity and authenticated archive-manifest verification.

Uses a pinned Ed25519 public key and a signed, canonical JSON manifest.
Cryptographic signatures establish control of a key, not that the key belongs
to a genuine independent archive. Trusted key onboarding is external.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("Invalid archive timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid archive timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Archive timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def verify_signed_archive(*, archive_path, research_path, manifest_path,
                          signature_path, trusted_ed25519_public_key,
                          expected_archive_id, decision_time):
    """Verify exact bytes, signature and chronology; fail closed on all errors.

    Manifest must contain archive_id, capture_time, publication_time,
    archive_sha256, research_sha256. Signature is base64 over raw manifest
    bytes; the trusted key is raw 32-byte Ed25519 key material.
    """
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise RuntimeError("cryptography package required for signed archive validation") from exc
    try:
        manifest_bytes = Path(manifest_path).read_bytes()
        manifest = json.loads(manifest_bytes)
        if not isinstance(manifest, dict) or set(manifest) != {
            "archive_id", "capture_time", "publication_time",
            "archive_sha256", "research_sha256"
        }:
            raise ValueError("Invalid archive manifest schema")
        if not isinstance(expected_archive_id, str) or not expected_archive_id.strip() or manifest["archive_id"] != expected_archive_id:
            raise ValueError("Archive identifier mismatch")
        signature = base64.b64decode(Path(signature_path).read_bytes(), validate=True)
        key = Ed25519PublicKey.from_public_bytes(trusted_ed25519_public_key)
        key.verify(signature, manifest_bytes)
    except InvalidSignature as exc:
        raise ValueError("Archive manifest signature invalid") from exc
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("Archive manifest authentication failed") from exc
    if not isinstance(decision_time, datetime) or decision_time.tzinfo is None or decision_time.utcoffset() is None:
        raise ValueError("Decision time must be timezone-aware")
    published = _utc(manifest["publication_time"])
    captured = _utc(manifest["capture_time"])
    decision = decision_time.astimezone(timezone.utc)
    if not published <= captured <= decision:
        raise ValueError("Archive not available before historical decision")
    archive_digest = hashlib.sha256(Path(archive_path).read_bytes()).hexdigest()
    research_digest = hashlib.sha256(Path(research_path).read_bytes()).hexdigest()
    if archive_digest != manifest["archive_sha256"] or research_digest != manifest["research_sha256"]:
        raise ValueError("Archive file-byte checksum mismatch")
    if archive_digest != research_digest:
        raise ValueError("Archived and research content differ")
    return {
        "status": "SIGNED_BYTES_AND_CHRONOLOGY_CONSISTENT",
        "archive_id": expected_archive_id,
        "sha256": archive_digest,
        "signature_valid_for_supplied_trusted_key": True,
        "archive_provider_identity_independently_verified": False,
        "historical_capture_independently_attested": False,
        "eligible_for_strategy_promotion": False,
    }
