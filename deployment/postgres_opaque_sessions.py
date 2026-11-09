"""PostgreSQL-backed opaque sessions; dedicated restricted session-store role required.

Schema must be installed by a migration operator on an isolated database.
The application role must have only SELECT/INSERT/DELETE on this table.
"""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS alpha_oidc_sessions (
 session_hash text PRIMARY KEY,
 owner_id text NOT NULL,
 expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS alpha_oidc_sessions_expiry ON alpha_oidc_sessions(expires_at);
"""

class PostgresOpaqueSessions:
    def __init__(self, connect, *, clock=None):
        if not callable(connect):
            raise ValueError("trusted PostgreSQL connection factory required")
        self.connect = connect
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _hash(token):
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token):
            raise PermissionError("invalid session")
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _owner(subject, issuer):
        if not isinstance(subject, str) or not 1 <= len(subject) <= 255 or not isinstance(issuer, str) or not issuer.startswith("https://"):
            raise PermissionError("invalid verified identity")
        return "oidc_" + hashlib.sha256((issuer.rstrip("/") + "\0" + subject).encode()).hexdigest()

    def create(self, subject, issuer):
        owner = self._owner(subject, issuer)
        token = secrets.token_urlsafe(48)
        expiry = self.clock() + timedelta(minutes=30)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO alpha_oidc_sessions(session_hash,owner_id,expires_at) VALUES (%s,%s,%s)",
                            (self._hash(token), owner, expiry))
        return token

    def resolve_owner(self, token):
        digest = self._hash(token)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT owner_id FROM alpha_oidc_sessions WHERE session_hash=%s AND expires_at>%s",
                            (digest, self.clock()))
                row = cur.fetchone()
        if not row or not re.fullmatch(r"oidc_[a-f0-9]{64}", row[0]):
            raise PermissionError("session revoked or expired")
        return row[0]

    def revoke(self, token):
        digest = self._hash(token)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM alpha_oidc_sessions WHERE session_hash=%s", (digest,))
