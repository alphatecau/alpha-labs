"""PostgreSQL-backed OIDC session store, research-only.

Requires a privately networked PostgreSQL service and psycopg 3. No schema
creation or deployment is performed by this module. Use reviewed migrations.
"""
import hashlib
import hmac
import secrets
import time


def _digest(value):
    if not isinstance(value, str) or len(value) < 20 or len(value) > 512:
        raise PermissionError("Invalid opaque credential")
    return hashlib.sha256(value.encode("ascii")).digest()


SCHEMA = """
CREATE TABLE IF NOT EXISTS oidc_pending (
  state BYTEA PRIMARY KEY, nonce BYTEA NOT NULL,
  verifier TEXT NOT NULL, expires_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS oidc_sessions (
  sid BYTEA PRIMARY KEY, subject TEXT NOT NULL,
  issuer TEXT NOT NULL, expires_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS oidc_pending_expiry ON oidc_pending(expires_at);
CREATE INDEX IF NOT EXISTS oidc_sessions_expiry ON oidc_sessions(expires_at);
"""


class PostgresOIDCStore:
    """Database connection factory is injected; never accepts client identity."""

    def __init__(self, connection_factory, *, now=None):
        if not callable(connection_factory):
            raise ValueError("Database connection factory required")
        self._connect = connection_factory
        self._now = now or (lambda: int(time.time()))

    def begin(self):
        state, nonce, verifier = (
            secrets.token_urlsafe(48), secrets.token_urlsafe(48),
            secrets.token_urlsafe(64))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO oidc_pending(state,nonce,verifier,expires_at) VALUES (%s,%s,%s,%s)",
                            (_digest(state), _digest(nonce), verifier, self._now() + 300))
        return state, nonce, verifier

    def consume(self, state, nonce):
        key = _digest(state)
        with self._connect() as conn:
            with conn.cursor() as cur:
                # Row-level lock and atomic deletion prevent concurrent replay.
                cur.execute("DELETE FROM oidc_pending WHERE state=%s RETURNING nonce,verifier,expires_at", (key,))
                row = cur.fetchone()
        if row is None or row[2] <= self._now() or not hmac.compare_digest(bytes(row[0]), _digest(nonce)):
            raise PermissionError("Unknown, expired or replayed login")
        return row[1]

    def create(self, subject, issuer, ttl=1800):
        if not isinstance(subject, str) or not subject or len(subject) > 255 or not isinstance(issuer, str) or not issuer or len(issuer) > 255 or type(ttl) is not int or not 0 < ttl <= 3600:
            raise PermissionError("Invalid session")
        sid = secrets.token_urlsafe(48)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO oidc_sessions(sid,subject,issuer,expires_at) VALUES (%s,%s,%s,%s)",
                            (_digest(sid), subject, issuer, self._now() + ttl))
        return sid

    def authenticate(self, sid):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT subject,issuer,expires_at FROM oidc_sessions WHERE sid=%s", (_digest(sid),))
                row = cur.fetchone()
        if row is None or row[2] <= self._now():
            raise PermissionError("Expired or revoked session")
        return row[0], row[1]

    def revoke(self, sid):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM oidc_sessions WHERE sid=%s", (_digest(sid),))

    def purge_expired(self):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM oidc_pending WHERE expires_at<=%s", (self._now(),))
                cur.execute("DELETE FROM oidc_sessions WHERE expires_at<=%s", (self._now(),))
