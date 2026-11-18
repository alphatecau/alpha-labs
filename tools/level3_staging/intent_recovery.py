"""Fail-closed recovery for a durable Level 3 intent and an idempotent local file.

The caller must first commit claim_with_audit() to PostgreSQL. This module never
accepts arbitrary paths and never marks a database intent complete on its own.
The filesystem must be durable and private; Render free ephemeral disk is NOT.
"""
import hashlib
import os
from pathlib import Path
from tools.level3_staging.postgres_custody import CustodyDenied, _check

class RecoveryConflict(CustodyDenied):
    pass

def reconcile_intent(root, nonce, path, digest, payload=None, fault=None):
    """Reconcile a committed intent without overwriting an existing file.

    If the target exists and matches its committed digest, return 'ready'.
    If missing, require original bytes, write via O_EXCL temp and atomic link,
    fsync the file and parent directory, then return 'ready'. Caller must
    complete_with_audit() separately; a crash at any point is retry-safe.
    """
    _check(nonce,path,digest)
    root=Path(root).resolve(strict=True)
    target=root.joinpath(*path.split("/"))
    if target.is_symlink():
        raise RecoveryConflict("symlink target denied")
    parent=target.parent
    if not parent.is_dir() or parent.is_symlink() or parent.resolve()!=parent:
        raise RecoveryConflict("untrusted parent directory")
    if target.exists():
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
            raise RecoveryConflict("existing file differs from committed intent")
        return "ready"
    if payload is None or not isinstance(payload,bytes) or hashlib.sha256(payload).hexdigest()!=digest:
        raise RecoveryConflict("original payload unavailable or digest mismatch")
    if len(payload)>32768:
        raise RecoveryConflict("payload exceeds limit")
    if fault=="before_write":
        raise RuntimeError("injected before write")
    temp=parent/("." + nonce + ".tmp")
    fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if fault=="after_temp":
            raise RuntimeError("injected after temp")
        os.link(temp,target,follow_symlinks=False)
        directory_fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        if fault=="after_link":
            raise RuntimeError("injected after link")
    finally:
        temp.unlink(missing_ok=True)
    return "ready"
