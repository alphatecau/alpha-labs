"""Strict Auth0 HTTPS code exchange; server-side use only."""
import json
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import urlsplit


class Auth0CodeExchanger:
    def __init__(self, *, issuer, client_id, client_secret, timeout=8):
        parsed = urlsplit(issuer)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.path not in ("", "/")
                or parsed.query or parsed.fragment or parsed.username or parsed.password):
            raise ValueError("invalid Auth0 issuer")
        if not client_id or not client_secret:
            raise ValueError("server-side Auth0 credentials required")
        self.url = issuer.rstrip("/") + "/oauth/token"
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout

    def __call__(self, *, code, code_verifier, redirect_uri, client_id):
        if client_id != self.client_id or not code or not code_verifier:
            raise PermissionError("invalid OAuth exchange")
        data = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
        }).encode()
        request = urllib.request.Request(self.url, data=data,
                                         headers={"Content-Type": "application/x-www-form-urlencoded"},
                                         method="POST")
        try:
            # Refuse redirects so token credentials cannot be forwarded elsewhere.
            opener = urllib.request.build_opener(_NoRedirect)
            with opener.open(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise PermissionError("token exchange rejected")
                body = response.read(65537)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise PermissionError("token exchange failed") from exc
        if len(body) > 65536:
            raise PermissionError("token response too large")
        try:
            result = json.loads(body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise PermissionError("invalid token response") from exc
        if not isinstance(result, dict) or not isinstance(result.get("id_token"), str):
            raise PermissionError("missing ID token")
        return result


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
