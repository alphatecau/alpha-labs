"""Offline custody uploader orchestration; never configures credentials or cloud access.

The injected adapter must implement find_by_name(parent_id, name), create(parent_id,
name, payload), and download(file_id). The caller is responsible for independently
authenticating the adapter, validating Drive owner/parent permissions and retaining
an external checkpoint. No remote operation is performed by importing this module.
"""
import hashlib

from tools.level3_staging.drive_readback import (
    CustodyReadbackDenied,
    verify_drive_readback,
)


def _check_file(record, parent_id, name):
    if not isinstance(record, dict):
        raise CustodyReadbackDenied("invalid Drive file record")
    if (not isinstance(record.get("id"), str) or not record["id"]
            or record.get("name") != name
            or record.get("parents") != [parent_id]
            or record.get("trashed") is not False):
        raise CustodyReadbackDenied("Drive file identity mismatch")
    return record["id"]


def upload_and_verify(adapter, parent_id, payload):
    """Create or recover one content-addressed object, then read back its bytes.

    A retry after an ambiguous upload must find exactly one matching object.
    Duplicate names are never accepted as proof of conditional creation.
    """
    if not isinstance(parent_id, str) or not parent_id:
        raise CustodyReadbackDenied("invalid parent folder")
    if not isinstance(payload, bytes):
        raise CustodyReadbackDenied("payload must be bytes")
    digest = hashlib.sha256(payload).hexdigest()
    name = digest + ".bin"
    matches = adapter.find_by_name(parent_id, name)
    if not isinstance(matches, list) or len(matches) > 1:
        raise CustodyReadbackDenied("ambiguous Drive object lookup")
    if len(matches) == 1:
        file_id = _check_file(matches[0], parent_id, name)
    else:
        try:
            created = adapter.create(parent_id, name, payload)
        except Exception:
            # The remote create may have succeeded despite a lost response.
            # Do not retry writes blindly: fail closed and reconcile on next run.
            raise CustodyReadbackDenied("ambiguous upload; reconcile before retry") from None
        file_id = _check_file(created, parent_id, name)
    # Re-query after creation/recovery to detect visible concurrent duplicates.\n    # This is detection, NOT atomic create-if-absent: eventual consistency\n    # and a concurrent writer can still race after this observation.\n    final_matches = adapter.find_by_name(parent_id, name)\n    if not isinstance(final_matches, list) or len(final_matches) != 1:\n        raise CustodyReadbackDenied("post-upload identity reconciliation failed")\n    if _check_file(final_matches[0], parent_id, name) != file_id:\n        raise CustodyReadbackDenied("post-upload file identity changed")\n    downloaded = adapter.download(file_id)
    result = verify_drive_readback(digest, payload, downloaded)
    return {"file_id": file_id, "parent_id": parent_id, "name": name, **result}
