"""Offline orchestration: reserve before upload; complete only after exact readback.

The database and Drive cannot share a transaction. On any failure the reservation
remains pending for independent reconciliation; no automatic release or retry.
"""
import hashlib
import uuid

from tools.level3_staging.drive_custody_upload import upload_and_verify
from tools.level3_staging.drive_upload_reservation import (
    complete_reservation,
    reserve,
)


def reserved_upload_and_verify(conn, adapter, parent_id, payload):
    if not isinstance(payload, bytes):
        raise ValueError("payload must be bytes")
    digest = hashlib.sha256(payload).hexdigest()
    owner_token = uuid.uuid4().hex
    reserve(conn, parent_id, digest, owner_token)
    # Any exception intentionally leaves the reservation pending.
    result = upload_and_verify(adapter, parent_id, payload)
    if (result.get("name") != digest + ".bin"
            or result.get("parent_id") != parent_id
            or result.get("sha256") != digest
            or result.get("size") != len(payload)
            or not isinstance(result.get("file_id"), str)
            or not result["file_id"]):
        raise ValueError("upload receipt identity or readback mismatch")
    # upload_and_verify already performed byte-for-byte SHA-256 readback.
    complete_reservation(conn, parent_id, digest, owner_token, result["file_id"])
    return result
