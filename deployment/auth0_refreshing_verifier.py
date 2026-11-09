"""Pinned Auth0 JWKS verifier with periodic refresh and fail-closed recovery.

Only the configured issuer is contacted. A failed refresh denies all tokens
until the next bounded refresh attempt; stale keys are never reused.
Unknown key IDs are rejected until a scheduled refresh succeeds.
"""
import threading
import time
from deployment.auth0_trusted_jwks import load_auth0_verifier


class RefreshingAuth0Verifier:
    def __init__(self, issuer, client_id, *, fetch=None, clock=None,
                 refresh_seconds=300):
        if type(refresh_seconds) is not int or not 30 <= refresh_seconds <= 3600:
            raise ValueError("invalid refresh interval")
        self._issuer, self._client_id = issuer, client_id
        self._fetch, self._clock = fetch, clock or time.monotonic
        self._interval = refresh_seconds
        self._lock = threading.RLock()
        self._verifier = load_auth0_verifier(issuer, client_id, fetch=fetch)
        self._last_refresh = self._clock()

    def __call__(self, token):
        with self._lock:
            now = self._clock()
            if now - self._last_refresh >= self._interval:
                self._verifier = None
                self._last_refresh = now
                try:
                    self._verifier = load_auth0_verifier(
                        self._issuer, self._client_id, fetch=self._fetch)
                except Exception as exc:
                    raise PermissionError("trusted JWKS refresh unavailable") from exc
            if self._verifier is None:
                raise PermissionError("trusted JWKS unavailable")
            return self._verifier(token)
