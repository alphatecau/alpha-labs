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
import re
import stat

MAX_MANIFEST_BYTES = 65536
MAX_SIGNATURE_BYTES = 4096
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024


def _bounded_bytes(path, limit):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Archive input must be a regular non-symlink file')
    if path.stat().st_size > limit:
        raise ValueError('Archive input exceeds size limit')
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Archive input exceeds size limit')
    return data


def _stream_sha256(path, limit):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Archive input must be a regular non-symlink file')
    digest = hashlib.sha256()
    total = 0
    with path.open('rb') as stream:
        if not stat.S_ISREG(__import__('os').fstat(stream.fileno()).st_mode):
            raise ValueError('Archive input must be regular file')
        while chunk := stream.read(1024 * 1024):
            total += len(chunk)
            if total > limit:
                raise ValueError('Archive input exceeds size limit')
            digest.update(chunk)
    return digest.hexdigest()


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
                          expected_archive_id, decision_time,
                          max_file_bytes=MAX_ARCHIVE_BYTES):
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
        manifest_bytes = _bounded_bytes(manifest_path, MAX_MANIFEST_BYTES)
        manifest = json.loads(manifest_bytes)
        if not isinstance(manifest, dict) or set(manifest) != {
            "archive_id", "capture_time", "publication_time",
            "archive_sha256", "research_sha256"
        }:
            raise ValueError("Invalid archive manifest schema")
        if not isinstance(expected_archive_id, str) or not expected_archive_id.strip() or manifest["archive_id"] != expected_archive_id:
            raise ValueError("Archive identifier mismatch")
        signature = base64.b64decode(_bounded_bytes(signature_path, MAX_SIGNATURE_BYTES), validate=True)
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
    if not isinstance(max_file_bytes, int) or isinstance(max_file_bytes, bool) or max_file_bytes < 1 or max_file_bytes > MAX_ARCHIVE_BYTES:
        raise ValueError('Invalid archive size limit')
    for field in ('archive_sha256', 'research_sha256'):
        if not isinstance(manifest[field], str) or re.fullmatch(r'[0-9a-f]{64}', manifest[field]) is None:
            raise ValueError('Invalid SHA-256 digest format')
    archive_digest = _stream_sha256(archive_path, max_file_bytes)
    research_digest = _stream_sha256(research_path, max_file_bytes)
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
