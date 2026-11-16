"""Offline asymmetric verification for signed, read-only Termux tasks.

Never accepts a private key, never executes a command, and does not alter v0.3.
Requires cryptography package. Signer and enrolment remain separate work.
"""
import base64
import json
import pathlib
import stat
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import signed_protocol_v4 as v4

DOMAIN = b"termux-v5-ed25519-task\x00"
ENVELOPE_FIELDS = frozenset({"task", "signature", "key_id"})
KEY_ID_FIELDS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")

def read_public_key(path):
    path = pathlib.Path(path)
    if path.is_symlink():
        raise v4.Rejected("public key symlink forbidden")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
        raise v4.Rejected("public key file not regular or writable by others")
    data = path.read_bytes()
    if len(data) != 32:
        raise v4.Rejected("public key must be 32 bytes")
    return Ed25519PublicKey.from_public_bytes(data)

def verify(envelope, public_keys, device, now=None):
    if type(envelope) is not dict or set(envelope) != ENVELOPE_FIELDS:
        raise v4.Rejected("invalid envelope")
    key_id = envelope["key_id"]
    if type(key_id) is not str or not 1 <= len(key_id) <= 64 or any(c not in KEY_ID_FIELDS for c in key_id):
        raise v4.Rejected("invalid key id")
    if key_id not in public_keys:
        raise v4.Rejected("untrusted signing key")
    signature = envelope["signature"]
    if type(signature) is not str:
        raise v4.Rejected("invalid signature")
    try:
        raw = base64.b64decode(signature, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise v4.Rejected("invalid signature encoding") from exc
    if len(raw) != 64 or base64.b64encode(raw).decode("ascii") != signature:
        raise v4.Rejected("noncanonical signature")
    task = envelope["task"]
    # Reuse strict task validation from v0.4, without invoking its HMAC check.
    if type(task) is not dict or set(task) != v4.FIELDS:
        raise v4.Rejected("invalid task fields")
    # Validate all schema and time rules with a temporary HMAC over the same task.
    # This is a local validation helper only, not an authorisation signature.
    temporary_key = b"\x00" * 32
    check = {"task": task, "signature": v4.signature_for(task, temporary_key)}
    v4.verify(check, temporary_key, device, now=now)
    key = public_keys[key_id]
    if not isinstance(key, Ed25519PublicKey):
        raise v4.Rejected("invalid trusted key")
    try:
        key.verify(raw, DOMAIN + key_id.encode("ascii") + b"\x00" + v4.canonical(task))
    except InvalidSignature as exc:
        raise v4.Rejected("signature mismatch") from exc
    return task

def authorize(envelope, public_keys, device, db, now=None):
    task = verify(envelope, public_keys, device, now=now)
    v4.reserve_nonce(db, task)
    return task
