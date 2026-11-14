"""Retrieve Auth0 signing keys from a pinned HTTPS issuer.

No caller-controlled URL, redirects or unbounded responses. This is an
explicit bootstrap operation, not a per-request network fallback.
"""
import json
import urllib.error
import urllib.request
from urllib.parse import urlsplit


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_auth0_jwks(issuer, *, timeout=8):
    parsed = urlsplit(issuer)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
            parsed.password or parsed.port not in (None, 443) or
            parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("exact HTTPS Auth0 issuer required")
    url = issuer.rstrip("/") + "/.well-known/jwks.json"
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, headers={"Accept": "application/json"}),
                         timeout=timeout) as response:
            if response.status != 200:
                raise PermissionError("JWKS fetch rejected")
            body = response.read(65537)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PermissionError("JWKS fetch unavailable") from exc
    if len(body) > 65536:
        raise PermissionError("JWKS response too large")
    try:
        jwks = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PermissionError("invalid JWKS") from exc
    if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list) or not jwks["keys"]:
        raise PermissionError("invalid JWKS")
    return jwks
