"""Fail-closed v0.4 HMAC task envelope verifier.

Not connected to worker_v2 or agent_v3. A signing key must never be published
to GitHub, committed to a repository, or sent through a GitHub issue.
"""
import hashlib
import hmac
import json
import re
import sqlite3
import time

OPS = frozenset({"repo_status", "repo_log"})
REPOS = frozenset({"alpha-labs", "Q3HASH"})
MAX_LIFETIME = 300
MAX_CLOCK_SKEW = 30
NONCE = re.compile(r"^[a-f0-9]{32}$")
DEVICE = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")
HEX = re.compile(r"^[a-f0-9]{64}$")
FIELDS = frozenset({"schema", "device", "nonce", "issued_at", "expires_at", "operation", "repo"})
ENVELOPE = frozenset({"task", "signature"})

class Rejected(ValueError):
    pass

def canonical(task):
    return json.dumps(task, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")

def signature_for(task, key):
    if not isinstance(key, bytes) or len(key) < 32:
        raise Rejected("invalid signing key")
    return hmac.new(key, b"termux-v4-task\x00" + canonical(task), hashlib.sha256).hexdigest()

def verify(envelope, key, device, now=None):
    if type(envelope) is not dict or set(envelope) != ENVELOPE:
        raise Rejected("invalid envelope")
    task = envelope["task"]
    sig = envelope["signature"]
    if type(task) is not dict or set(task) != FIELDS:
        raise Rejected("invalid task fields")
    if type(sig) is not str or not HEX.fullmatch(sig):
        raise Rejected("invalid signature encoding")
    if type(device) is not str or not DEVICE.fullmatch(device):
        raise Rejected("invalid local device")
    if type(task["schema"]) is not int or task["schema"] != 4:
        raise Rejected("unsupported schema")
    if type(task["device"]) is not str or task["device"] != device:
        raise Rejected("wrong device")
    if type(task["nonce"]) is not str or not NONCE.fullmatch(task["nonce"]):
        raise Rejected("invalid nonce")
    if type(task["operation"]) is not str or task["operation"] not in OPS:
        raise Rejected("operation denied")
    if type(task["repo"]) is not str or task["repo"] not in REPOS:
        raise Rejected("repository denied")
    issued, expiry = task["issued_at"], task["expires_at"]
    if type(issued) is not int or type(expiry) is not int:
        raise Rejected("timestamps must be integers")
    current = int(time.time()) if now is None else now
    if issued > current + MAX_CLOCK_SKEW or expiry <= current:
        raise Rejected("future or expired task")
    if expiry <= issued or expiry - issued > MAX_LIFETIME:
        raise Rejected("invalid lifetime")
    expected = signature_for(task, key)
    if not hmac.compare_digest(expected, sig):
        raise Rejected("signature mismatch")
    return task

def reserve_nonce(db, task):
    """Reserve exactly once; database must be durable and private to the agent."""
    db.execute("CREATE TABLE IF NOT EXISTS v4_nonces (nonce TEXT PRIMARY KEY, expires_at INTEGER NOT NULL)")
    try:
        with db:
            db.execute("INSERT INTO v4_nonces (nonce, expires_at) VALUES (?, ?)",
                       (task["nonce"], task["expires_at"]))
    except sqlite3.IntegrityError as exc:
        raise Rejected("replayed nonce") from exc
    return True

def authorize(envelope, key, device, db, now=None):
    task = verify(envelope, key, device, now=now)
    reserve_nonce(db, task)
    return task
