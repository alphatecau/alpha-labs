"""Fail-closed trusted-proxy ingress normalisation for isolated staging.

Only call after independently authenticating the immediate reverse proxy hop.
Do not infer proxy trust from forwarded headers themselves.
"""
from urllib.parse import urlsplit


def canonicalise_proxy_environ(environ, *, trusted_peer, expected_origin):
    if not trusted_peer:
        raise PermissionError("Untrusted proxy peer")
    parsed = urlsplit(expected_origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Explicit canonical HTTPS origin required")
    allowed_host = parsed.netloc
    forwarded = ("HTTP_FORWARDED", "HTTP_X_FORWARDED_HOST", "HTTP_X_FORWARDED_PROTO")
    if any(environ.get(k) for k in forwarded):
        raise PermissionError("Forwarded client metadata forbidden")
    if environ.get("HTTP_HOST") != allowed_host:
        raise PermissionError("Host mismatch")
    result = dict(environ)
    result["wsgi.url_scheme"] = "https"
    for key in forwarded:
        result.pop(key, None)
    return result
