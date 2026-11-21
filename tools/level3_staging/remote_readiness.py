"""Fail-closed remote Level 3 readiness observer.

This module does NOT authorise, sign, execute, or relay writes. It only checks
whether a remote service explicitly reports readiness; it never converts a
health response into an approval to start Level 3.
"""
import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class RemoteNotReady(Exception):
    """The remote broker cannot be trusted as ready."""


def observe_readiness(origin, *, timeout=5, opener=None):
    parsed = urlsplit(origin) if isinstance(origin, str) else None
    if (
        parsed is None or parsed.scheme != "https" or not parsed.hostname
        or parsed.username is not None or parsed.password is not None
        or parsed.query or parsed.fragment or parsed.path not in ("", "/")
    ):
        raise RemoteNotReady("invalid HTTPS broker origin")
    url = origin.rstrip("/") + "/readyz"
    request = Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        if opener is None:
            response = urlopen(request, timeout=timeout, context=ssl.create_default_context())
        else:
            response = opener(request, timeout=timeout)
        with response:
            status = response.status
            payload = response.read(4097)
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    except (HTTPError, URLError, OSError, TimeoutError, ValueError) as exc:
        raise RemoteNotReady("broker readiness unavailable") from exc
    if status != 200 or len(payload) > 4096 or content_type != "application/json":
        raise RemoteNotReady("broker readiness denied")
    try:
        result = json.loads(payload)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RemoteNotReady("invalid readiness response") from exc
    if not isinstance(result, dict) or result.get("ready") is not True:
        raise RemoteNotReady("broker not ready")
    # An unauthenticated JSON 'ready:true' is not a signed readiness attestation.
    # Never grant write capability based on this observation.
    return {"reachable": True, "reported_ready": True, "authorised": False}
