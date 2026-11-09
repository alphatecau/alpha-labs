"""Strict staging Auth0/Render configuration validation (no secrets logged)."""
import os
import urllib.parse


def staging_auth0_settings(environ=None):
    env = os.environ if environ is None else environ
    issuer = env.get("AUTH0_ISSUER", "")
    client_id = env.get("AUTH0_CLIENT_ID", "")
    callback = env.get("AUTH0_CALLBACK_URL", "")
    dashboard = env.get("ALPHA_BFF_ORIGIN", "")
    parsed = [urllib.parse.urlsplit(v) for v in (issuer, callback, dashboard)]
    if any(p.scheme != "https" or not p.hostname or p.username or p.password or p.query or p.fragment for p in parsed):
        raise ValueError("HTTPS-only trusted Auth0 configuration required")
    if parsed[0].path not in ("", "/") or parsed[2].path not in ("", "/"):
        raise ValueError("issuer and BFF must be origins")
    if parsed[1].path != "/auth/callback" or (parsed[1].scheme, parsed[1].netloc) != (parsed[2].scheme, parsed[2].netloc):
        raise ValueError("callback must match BFF origin")
    if not isinstance(client_id, str) or not 8 <= len(client_id) <= 256:
        raise ValueError("invalid client identifier")
    if parsed[0].hostname == parsed[2].hostname:
        raise ValueError("issuer and BFF must be separate")
    return {"issuer": issuer.rstrip("/"), "client_id": client_id,
            "redirect_uri": callback, "bff_origin": dashboard.rstrip("/")}
