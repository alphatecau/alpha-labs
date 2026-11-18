"""Offline create-only staging service. NOT deployed or network-exposed."""
import base64
import hashlib
import json
import os
import re
import sqlite3
import stat
import time
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ALLOW = re.compile(r"^(docs/level3-staging/[A-Za-z0-9_-]+\.md|tests/level3-staging/[A-Za-z0-9_-]+\.txt)$")
MAX_BYTES = 32768

class Denied(Exception):
    pass

def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")

def validate(path, content):
    if not isinstance(path, str) or not ALLOW.fullmatch(path) or not isinstance(content, str):
        raise Denied("invalid request")
    payload = content.encode("utf-8")
    if len(payload) > MAX_BYTES:
        raise Denied("too large")
    return payload, hashlib.sha256(payload).hexdigest()

def _parent(root, path):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(root, flags)
    try:
        for part in path.split("/")[:-1]:
            nxt = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd, path.split("/")[-1]
    except BaseException:
        os.close(fd)
        raise

def _database(db_path):
    db_path = Path(db_path)
    if db_path.is_symlink():
        raise Denied("symlink database")
    if db_path.exists():
        st = db_path.stat()
        if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077:
            raise Denied("database permissions")
    old = os.umask(0o077)
    try:
        con = sqlite3.connect(str(db_path), isolation_level=None, timeout=5)
    finally:
        os.umask(old)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    con.execute("CREATE TABLE IF NOT EXISTS claims (nonce TEXT PRIMARY KEY, state TEXT NOT NULL CHECK(state IN ('claimed','complete')))")
    return con

def apply(root, db_path, public_key_bytes, approval, signature_b64, path, content, now=None):
    payload, digest = validate(path, content)
    root = Path(root).resolve(strict=True)
    db_path = Path(db_path)
    if db_path.parent.resolve().is_relative_to(root):
        raise Denied("ledger must be outside workspace")
    if not isinstance(approval, dict) or set(approval) != {"operation","path","sha256","nonce","expires_at"}:
        raise Denied("invalid approval fields")
    nonce = approval["nonce"]
    clock = int(time.time() if now is None else now)
    if not (approval["operation"] == "create" and approval["path"] == path and approval["sha256"] == digest
            and isinstance(nonce, str) and re.fullmatch("[a-f0-9]{64}", nonce)
            and type(approval["expires_at"]) is int and clock < approval["expires_at"] <= clock + 600):
        raise Denied("approval mismatch or expired")
    try:
        sig = base64.b64decode(signature_b64, validate=True)
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(sig, canonical(approval))
    except (ValueError, TypeError, InvalidSignature) as exc:
        raise Denied("invalid signature") from exc
    audit_path = os.environ.get("LEVEL3_AUDIT_PATH")
    if audit_path:
        from tools.level3_staging.audit_chain import append, verify
        if Path(audit_path).parent.resolve().is_relative_to(root):
            raise Denied("audit must be outside workspace")
        verify(audit_path)
    con = _database(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("INSERT INTO claims(nonce,state) VALUES (?,?)", (nonce, "claimed"))
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    if audit_path:
        append(audit_path, {"phase":"claimed","nonce":nonce,"path":path,"sha256":digest})
    fd, name = _parent(root, path)
    try:
        out = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd)
        with os.fdopen(out, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(fd)
    finally:
        os.close(fd)
    con = _database(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        updated = con.execute("UPDATE claims SET state='complete' WHERE nonce=? AND state='claimed'", (nonce,)).rowcount
        if updated != 1:
            raise Denied("claim state changed")
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    if audit_path:
        append(audit_path, {"phase":"complete","nonce":nonce,"path":path,"sha256":digest})
    return {"path":path,"sha256":digest,"nonce":nonce,"status":"complete"}
