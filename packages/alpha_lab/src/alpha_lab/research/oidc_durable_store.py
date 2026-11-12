"""Research-only durable OIDC session and transaction store.

SQLite persistence survives process restarts; use a dedicated private persistent
volume. Opaque secrets are stored only as SHA-256 digests. No trade permissions.
"""
import hashlib
import hmac
import secrets
import sqlite3
import time


def digest(value):
    if not isinstance(value, str) or len(value) < 20:
        raise PermissionError("Invalid opaque credential")
    return hashlib.sha256(value.encode("ascii")).digest()


class DurableOIDCStore:
    def __init__(self, path, now=None):
        self.now = now or (lambda: int(time.time()))
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("CREATE TABLE IF NOT EXISTS pending (state BLOB PRIMARY KEY, nonce BLOB NOT NULL, verifier TEXT NOT NULL, expires INTEGER NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS sessions (sid BLOB PRIMARY KEY, subject TEXT NOT NULL, issuer TEXT NOT NULL, expires INTEGER NOT NULL)")

    def begin(self):
        state, nonce, verifier = (secrets.token_urlsafe(48), secrets.token_urlsafe(48), secrets.token_urlsafe(64))
        self.db.execute("INSERT INTO pending VALUES (?,?,?,?)",
                        (digest(state), digest(nonce), verifier, self.now() + 300))
        return state, nonce, verifier

    def consume(self, state, nonce):
        key = digest(state)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT nonce,verifier,expires FROM pending WHERE state=?", (key,)).fetchone()
            self.db.execute("DELETE FROM pending WHERE state=?", (key,))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        if row is None or row[2] <= self.now() or not hmac.compare_digest(row[0], digest(nonce)):
            raise PermissionError("Invalid or replayed OIDC transaction")
        return row[1]

    def create(self, subject, issuer, ttl=1800):
        if not isinstance(subject, str) or not subject or not isinstance(issuer, str) or not issuer or type(ttl) is not int or not 0 < ttl <= 3600:
            raise PermissionError("Invalid session")
        sid = secrets.token_urlsafe(48)
        self.db.execute("INSERT INTO sessions VALUES (?,?,?,?)",
                        (digest(sid), subject, issuer, self.now() + ttl))
        return sid

    def authenticate(self, sid):
        row = self.db.execute("SELECT subject,issuer,expires FROM sessions WHERE sid=?", (digest(sid),)).fetchone()
        if row is None or row[2] <= self.now():
            raise PermissionError("Session expired or revoked")
        return row[0], row[1]

    def revoke(self, sid):
        self.db.execute("DELETE FROM sessions WHERE sid=?", (digest(sid),))

    def close(self):
        self.db.close()
