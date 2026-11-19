"""Fail-closed offline verification for Google Drive custody object readback.

This module has no Google credentials or network access. The independent
uploader must supply bytes fetched from Drive using its own identity.
"""
import hashlib
import re


class CustodyReadbackDenied(ValueError):
    """The retrieved custody object does not match the committed evidence."""


def verify_drive_readback(expected_sha256, uploaded_bytes, downloaded_bytes):
    """Verify the exact bytes returned by an independent Drive readback.

    Do not substitute provider metadata, ETags or a locally cached upload
    buffer for downloaded_bytes. Caller must verify the Drive file identity,
    owner and expected parent folder separately.
    """
    if not isinstance(expected_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise CustodyReadbackDenied("invalid expected SHA-256")
    if not isinstance(uploaded_bytes, bytes) or not isinstance(downloaded_bytes, bytes):
        raise CustodyReadbackDenied("readback must contain raw bytes")
    upload_digest = hashlib.sha256(uploaded_bytes).hexdigest()
    readback_digest = hashlib.sha256(downloaded_bytes).hexdigest()
    if upload_digest != expected_sha256 or readback_digest != expected_sha256:
        raise CustodyReadbackDenied("custody object digest mismatch")
    return {"sha256": readback_digest, "size": len(downloaded_bytes)}
