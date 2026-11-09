"""Fail-closed trusted-proxy ingress normalisation for isolated staging.

Only call after independently authenticating the immediate reverse proxy hop.
Do not infer proxy trust from forwarded headers themselves.
"""
from urllib.parse import urlsplit
from ipaddress import ip_address, ip_network


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

def canonicalise_verified_peer(environ, *, trusted_peer_cidrs, expected_origin):
    """Check the socket peer address, not caller-supplied forwarded headers.

    CIDRs must be operator-reviewed and limited to actual trusted ingress peers.
    A direct internet client must never be able to reach this WSGI process.
    """
    if not isinstance(trusted_peer_cidrs, (tuple, list)) or not trusted_peer_cidrs:
        raise ValueError("Explicit trusted peer CIDRs required")
    try:
        peer = ip_address(environ["REMOTE_ADDR"])
        networks = [ip_network(cidr, strict=True) for cidr in trusted_peer_cidrs]
    except (KeyError, TypeError, ValueError) as exc:
        raise PermissionError("Invalid ingress peer configuration") from exc
    if not any(peer in network for network in networks):
        raise PermissionError("Untrusted ingress peer")
    return canonicalise_proxy_environ(
        environ, trusted_peer=True, expected_origin=expected_origin)
