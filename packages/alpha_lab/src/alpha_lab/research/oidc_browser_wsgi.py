"""Research-only Auth0 Authorization Code + PKCE browser WSGI adapter.

No deployment entry point is supplied. Intended for reviewed HTTPS staging only.
Requires explicit server configuration and an injected verified JWT verifier.
"""
import base64
import hashlib
import json
import secrets
from http.cookies import SimpleCookie
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from alpha_lab.research.auth0_jwt import Auth0JWTVerifier
from alpha_lab.research.oidc_durable_store import DurableOIDCStore
from alpha_lab.research.oidc_postgres_store import PostgresOIDCStore


class _RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PermissionError("Token endpoint redirect rejected")


def _validated_origin(url):
    parts = urlsplit(url)
    if (parts.scheme != "https" or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.query or parts.fragment
            or parts.port not in (None, 443)):
        raise ValueError("Invalid HTTPS origin")
    return parts.scheme + "://" + parts.netloc


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _claims(token):
    try:
        return json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "==="))
    except (ValueError, IndexError, UnicodeError) as exc:
        raise PermissionError("Invalid ID token") from exc


class OIDCBrowserWSGI:
    def __init__(self, *, issuer, client_id, client_secret, redirect_uri, store, verifier, exchange=None, now=None):
        if not isinstance(issuer, str) or not issuer.startswith("https://") or not issuer.endswith("/") or "?" in issuer or "#" in issuer:
            raise ValueError("HTTPS OIDC issuer required")
        if not isinstance(redirect_uri, str) or not redirect_uri.endswith("/auth/callback") or urlsplit(redirect_uri).path != "/auth/callback":
            raise ValueError("HTTPS callback required")
        if not all(isinstance(x, str) and x for x in (client_id, client_secret)):
            raise ValueError("Confidential client credentials required")
        if not isinstance(store, (DurableOIDCStore, PostgresOIDCStore)) or not isinstance(verifier, Auth0JWTVerifier) or verifier.issuer != issuer or verifier.audience != client_id:
            raise ValueError("Verified OIDC identity and durable store required")
        self.issuer, self.client_id, self.client_secret = issuer, client_id, client_secret
        self.redirect_uri, self.store, self.verifier = redirect_uri, store, verifier
        self.origin = _validated_origin(redirect_uri)
        self.exchange = exchange or self._exchange
        self.now = now

    def _exchange(self, code, verifier):
        body = urlencode({"grant_type": "authorization_code", "client_id": self.client_id,
                          "client_secret": self.client_secret, "code": code,
                          "code_verifier": verifier, "redirect_uri": self.redirect_uri}).encode()
        req = Request(self.issuer + "oauth/token", data=body,
                      headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        with build_opener(_RejectRedirect()).open(req, timeout=8) as response:
            if response.status != 200:
                raise PermissionError("Token exchange rejected")
            payload = response.read(16385)
            if len(payload) > 16384:
                raise PermissionError("Token response too large")
            return json.loads(payload)

    def __call__(self, env, start_response):
        def respond(status, payload=b"", headers=()):
            if isinstance(payload, dict):
                payload = json.dumps(payload).encode()
                mime = "application/json"
            else:
                mime = "text/plain; charset=utf-8"
            start_response(status, [("Content-Type", mime), ("Content-Length", str(len(payload))),
                                    ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                                    ("Referrer-Policy", "no-referrer"), *headers])
            return [payload]

        def cookie(name, value, max_age):
            return ("Set-Cookie", f"{name}={value}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age={max_age}")

        def get_cookie(name):
            jar = SimpleCookie()
            jar.load(env.get("HTTP_COOKIE", ""))
            return jar[name].value if name in jar else None

        path, method = env.get("PATH_INFO"), env.get("REQUEST_METHOD")
        if env.get("wsgi.url_scheme") != "https":
            return respond("403 Forbidden", {"error": "https_required"})
        if path == "/auth/login" and env.get("QUERY_STRING"):
            return respond("400 Bad Request", {"error": "query_not_supported"})
        if path == "/auth/login" and method == "GET":
            state, nonce, verifier = self.store.begin()
            challenge = _b64(hashlib.sha256(verifier.encode()).digest())
            url = self.issuer + "authorize?" + urlencode({
                "response_type": "code", "client_id": self.client_id,
                "redirect_uri": self.redirect_uri, "scope": "openid",
                "state": state, "nonce": nonce, "code_challenge": challenge,
                "code_challenge_method": "S256"})
            # Bind state and nonce to the initiating browser; neither is accepted
            # solely from an untrusted callback query.
            return respond("302 Found", headers=[("Location", url),
                cookie("__Host-alpha_oidc", state + "." + nonce, 300)])
        if path == "/auth/callback" and method == "GET":
            from urllib.parse import parse_qs
            try:
                query = parse_qs(env.get("QUERY_STRING", ""), strict_parsing=True)
                if set(query) != {"code", "state"} or any(len(v) != 1 for v in query.values()):
                    raise PermissionError("Unexpected callback parameters")
                code, state = query["code"][0], query["state"][0]
                if not 1 <= len(code) <= 4096:
                    raise PermissionError("Invalid authorization code")
                binding = get_cookie("__Host-alpha_oidc")
                if not binding or not secrets.compare_digest(binding.split(".", 1)[0], state):
                    raise PermissionError("Unbound callback")
                nonce = binding.split(".", 1)[1]
                verifier = self.store.consume(state, nonce)
                tokens = self.exchange(code, verifier)
                if not isinstance(tokens, dict) or not isinstance(tokens.get("id_token"), str):
                    raise PermissionError("Missing ID token")
                import datetime
                now = self.now or datetime.datetime.now(datetime.timezone.utc)
                principal = self.verifier.verify(tokens["id_token"], now=now)
                claims = _claims(tokens["id_token"])
                if not isinstance(claims.get("nonce"), str) or not secrets.compare_digest(claims["nonce"], nonce):
                    raise PermissionError("ID token nonce mismatch")
                sid = self.store.create(principal.subject, principal.issuer)
                return respond("303 See Other", headers=[
                    ("Location", "/auth/me"), cookie("__Host-alpha_session", sid, 1800),
                    cookie("__Host-alpha_oidc", "", 0)])
            except (PermissionError, ValueError, KeyError, TypeError, IndexError, OSError, HTTPError, URLError):
                return respond("401 Unauthorized", {"error": "authentication_failed"},
                               [cookie("__Host-alpha_oidc", "", 0)])
        if path == "/auth/me" and method == "GET":
            try:
                subject, issuer = self.store.authenticate(get_cookie("__Host-alpha_session"))
                return respond("200 OK", {"authenticated": True, "subject": subject})
            except (PermissionError, ValueError, TypeError):
                return respond("401 Unauthorized", {"authenticated": False})
        if path == "/auth/logout" and method == "POST":
            if env.get("HTTP_ORIGIN") != self.origin:
                return respond("403 Forbidden", {"error": "csrf_rejected"})
            try:
                self.store.revoke(get_cookie("__Host-alpha_session"))
            except (PermissionError, ValueError, TypeError):
                pass
            return respond("204 No Content", headers=[cookie("__Host-alpha_session", "", 0)])
        return respond("404 Not Found", {"error": "not_found"})
