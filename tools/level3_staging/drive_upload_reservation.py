"""Database-backed content-addressed upload reservations (offline helper).

Requires a separately migrated level3_custody.drive_upload_reservation table
with PRIMARY KEY (parent_id, sha256). The database reserves ownership, but
cannot atomically commit a Google Drive upload. Failed/ambiguous uploads stay
reserved until a separately reviewed recovery procedure reconciles them.
"""
import re


class UploadReservationDenied(ValueError):
    pass


_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_OWNER = re.compile(r"^[0-9a-f]{32}$")


def reserve(conn, parent_id, sha256, owner_token):
    if not isinstance(parent_id, str) or not parent_id or len(parent_id) > 256:
        raise UploadReservationDenied("invalid parent id")
    if not isinstance(sha256, str) or not _DIGEST.fullmatch(sha256):
        raise UploadReservationDenied("invalid content digest")
    if not isinstance(owner_token, str) or not _OWNER.fullmatch(owner_token):
        raise UploadReservationDenied("invalid reservation owner")
    with conn.transaction():
        row = conn.execute(
            "INSERT INTO level3_custody.drive_upload_reservation "
            "(parent_id,sha256,owner_token,state) VALUES (%s,%s,%s,'reserved') "
            "ON CONFLICT (parent_id,sha256) DO NOTHING RETURNING owner_token",
            (parent_id, sha256, owner_token),
        ).fetchone()
        if row is None:
            raise UploadReservationDenied("content already reserved; manual reconciliation required")
    return {"parent_id": parent_id, "sha256": sha256, "state": "reserved"}


def complete_reservation(conn, parent_id, sha256, owner_token, file_id):
    if not isinstance(file_id, str) or not file_id or len(file_id) > 256:
        raise UploadReservationDenied("invalid file id")
    if not isinstance(parent_id, str) or not parent_id or len(parent_id) > 256:
        raise UploadReservationDenied("invalid parent id")
    if not isinstance(sha256, str) or not _DIGEST.fullmatch(sha256):
        raise UploadReservationDenied("invalid content digest")
    if not isinstance(owner_token, str) or not _OWNER.fullmatch(owner_token):
        raise UploadReservationDenied("invalid reservation owner")
    with conn.transaction():
        row = conn.execute(
            "UPDATE level3_custody.drive_upload_reservation "
            "SET state='verified',file_id=%s,verified_at=now() "
            "WHERE parent_id=%s AND sha256=%s AND owner_token=%s "
            "AND state='reserved' RETURNING file_id",
            (file_id, parent_id, sha256, owner_token),
        ).fetchone()
        if row is None:
            raise UploadReservationDenied("reservation missing, stolen or already completed")
    return {"parent_id": parent_id, "sha256": sha256, "file_id": file_id, "state": "verified"}
