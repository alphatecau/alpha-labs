"""Fail-closed Google Drive evidence adapter (offline contract; no OAuth credentials).

This is NOT an immutable/WORM store and is NOT a production custody gate.
An independently controlled auditor must validate and anchor every receipt.
The injected client implements create(parent_id,name,bytes)->file_id and
read(file_id)->bytes. Never expose auditor credentials to a broker.
"""
import hashlib
import re

class DriveCustodyDenied(ValueError):
    pass

_ID = re.compile(r"^[A-Za-z0-9_-]{10,128}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_NAME = re.compile(r"^[a-f0-9]{64}\.bin$")

def _validate(folder_id, nonce, digest, payload):
    if not isinstance(folder_id, str) or not _ID.fullmatch(folder_id):
        raise DriveCustodyDenied("invalid destination folder")
    if not isinstance(nonce, str) or not _DIGEST.fullmatch(nonce):
        raise DriveCustodyDenied("invalid nonce")
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        raise DriveCustodyDenied("invalid digest")
    if type(payload) is not bytes or len(payload) > 32768:
        raise DriveCustodyDenied("invalid payload")
    if hashlib.sha256(payload).hexdigest() != digest:
        raise DriveCustodyDenied("payload digest mismatch")

def create_and_verify(client, folder_id, nonce, digest, payload):
    """Create a uniquely named object and read back its bytes before receipt.

    A network timeout after create is ambiguous: caller MUST reconcile using
    independently verified provider metadata; never blindly retry a create.
    """
    _validate(folder_id, nonce, digest, payload)
    name = nonce + ".bin"
    if not _NAME.fullmatch(name):
        raise DriveCustodyDenied("invalid object name")
    try:
        file_id = client.create(folder_id, name, payload)
    except Exception as exc:
        raise DriveCustodyDenied("create failed or outcome unknown; reconcile before retry") from exc
    if not isinstance(file_id, str) or not _ID.fullmatch(file_id):
        raise DriveCustodyDenied("provider returned invalid object id")
    try:
        observed = client.read(file_id)
    except Exception as exc:
        raise DriveCustodyDenied("readback unavailable; do not complete intent") from exc
    if type(observed) is not bytes or hashlib.sha256(observed).hexdigest() != digest:
        raise DriveCustodyDenied("readback digest mismatch")
    return {"provider": "google_drive", "folder_id": folder_id,
            "object_id": file_id, "object_name": name, "sha256": digest,
            "size": len(payload), "auditor_anchor_verified": False}
