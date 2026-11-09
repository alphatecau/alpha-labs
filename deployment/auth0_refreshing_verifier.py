"""Bounded, pinned Auth0 JWKS refresh for key rotation.

Only the configured issuer is contacted. Refresh on unknown kid is rate-limited,
and network errors fail closed; never trust token-provided URLs.
"""
import threading
import time
from deployment.auth0_trusted_jwks import load_auth0_verifier


class RefreshingAuth0Verifier:
    def __init__(self, issuer, client_id, *, fetch=None, clock=None,
                 refresh_seconds=300):
        if not isinstance(refresh_seconds, int) or not 30 <= refresh_seconds <= 3600:
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
                # Do not retain stale keys when refresh is due but fails.
                self._verifier = None
                self._last_refresh = now
                self._verifier = load_auth0_verifier(
                    self._issuer, self._client_id, fetch=self._fetch)
            if self._verifier is None:
                raise PermissionError("trusted JWKS unavailable")
            return self._verifier(token)
