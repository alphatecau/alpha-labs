"""Server-only OIDC transaction and session primitives; no HTTP routes.

This module intentionally does not exchange authorisation codes or issue login
cookies. The eventual web adapter must use HTTPS, HttpOnly, Secure, SameSite
cookies, CSRF protection and server-side token verification.
"""
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PendingLogin:
    state_hash: bytes
    nonce_hash: bytes
    verifier: str
    expires_at: int


@dataclass(frozen=True)
class Session:
    subject: str
    issuer: str
    expires_at: int


class SessionRegistry:
    """Single-process reference implementation; not durable or deployable."""

    def __init__(self, *, now=None):
        self._now = now or (lambda: int(time.time()))
        self._pending = {}
        self._sessions = {}

    @staticmethod
    def _hash(value):
        if not isinstance(value, str) or not value:
            raise PermissionError("Missing authentication value")
        return hashlib.sha256(value.encode()).digest()

    def begin(self):
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        self._pending[self._hash(state)] = PendingLogin(
            self._hash(state), self._hash(nonce), verifier, self._now() + 300)
        return state, nonce, verifier

    def consume(self, state, nonce):
        key = self._hash(state)
        pending = self._pending.pop(key, None)
        if pending is None or self._now() >= pending.expires_at:
            raise PermissionError("Unknown, replayed or expired login")
        if not hmac.compare_digest(self._hash(nonce), pending.nonce_hash):
            raise PermissionError("OIDC nonce mismatch")
        return pending.verifier

    def create_session(self, *, subject, issuer, expires_at):
        if not isinstance(subject, str) or not subject or not isinstance(issuer, str) or not issuer:
            raise PermissionError("Verified principal required")
        if type(expires_at) is not int or expires_at <= self._now() or expires_at > self._now() + 3600:
            raise PermissionError("Invalid session lifetime")
        sid = secrets.token_urlsafe(48)
        self._sessions[self._hash(sid)] = Session(subject, issuer, expires_at)
        return sid

    def authenticate(self, sid):
        key = self._hash(sid)
        session = self._sessions.get(key)
        if session is None or self._now() >= session.expires_at:
            self._sessions.pop(key, None)
            raise PermissionError("Missing or expired session")
        return session

    def revoke(self, sid):
        self._sessions.pop(self._hash(sid), None)
