"""Research-only authenticated staging WSGI composition; never deploy without review.

All security-sensitive services are injected: verified OIDC controller, durable
session repository, per-tenant credential broker and read-only research reader.
No implicit environment or database fallback.
"""
import hashlib
import hmac
import json
import re
import secrets
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit

from alpha_lab.research.postgres_paper_security import PostgresIdentityLimiter, RateLimitExceeded
from deployment.account_role_research_reader import AccountRoleResearchReader


class StagingResearchBFF:
    def __init__(self, flow, controller, sessions, reader, *, origin, authorize_owner, rate_limiter):
        parsed = urlsplit(origin)
        if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment:
            raise ValueError("exact HTTPS origin required")
        if not isinstance(rate_limiter, PostgresIdentityLimiter):
            raise ValueError("shared PostgreSQL rate limiter required")
        if any(component is None for component in (flow, controller, sessions, reader)):
            raise ValueError("all authenticated dependencies required")
        if not callable(authorize_owner):
            raise ValueError("current ownership authorizer required")
        if not isinstance(reader, AccountRoleResearchReader):
            raise ValueError("tenant-role research reader required")
        self.flow, self.controller, self.sessions, self.reader = flow, controller, sessions, reader
        self.authorize_owner = authorize_owner
        self.origin = origin.rstrip("/")
        self.rate_limiter = rate_limiter

    def __call__(self, env, start_response):
        def reply(status, data=b"", headers=()):
            base = [("Content-Length", str(len(data))), ("Cache-Control", "no-store"),
                    ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"),
                    ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")]
            start_response(status, base + list(headers))
            return [data]

        path, method = env.get("PATH_INFO", ""), env.get("REQUEST_METHOD", "")
        if path == "/healthz" and method == "GET":
            return reply("200 OK", b'{"status":"ok","trading":"disabled"}',
                         [("Content-Type", "application/json")])
        if path == "/auth/login" and method == "GET":
            url = self.flow.begin()
            params = parse_qs(urlsplit(url).query)
            state = params["state"][0]
            # Bind the single-use server-side state to the initiating browser.
            cookie = "__Host-alpha_oauth_state=" + state + "; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=300"
            return reply("302 Found", headers=[("Location", url), ("Set-Cookie", cookie)])
        if path == "/auth/callback" and method == "GET":
            params = parse_qs(env.get("QUERY_STRING", ""), keep_blank_values=True)
            if set(params) != {"code", "state"} or any(len(v) != 1 for v in params.values()):
                return reply("401 Unauthorized")
            state_cookie = self._cookie(env, "__Host-alpha_oauth_state")
            state = params["state"][0]
            if not state_cookie or not hmac.compare_digest(state_cookie, state):
                return reply("401 Unauthorized")
            try:
                session_cookie = self.controller.complete(state, params["code"][0])
            except Exception:
                return reply("401 Unauthorized", headers=[("Set-Cookie", self._clear_state())])
            return reply("303 See Other", headers=[
                ("Location", self.origin + "/"),
                ("Set-Cookie", self._clear_state()),
                ("Set-Cookie", session_cookie)])
        if path == "/auth/logout" and method == "POST":
            if env.get("HTTP_ORIGIN") != self.origin:
                return reply("403 Forbidden")
            sid = self._cookie(env, "__Host-alpha_session")
            if sid:
                try:
                    self.sessions.revoke(sid)
                except Exception:
                    return reply("503 Service Unavailable")
            return reply("204 No Content", headers=[
                ("Set-Cookie", "__Host-alpha_session=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0")])
        if path in ("/api/v1/research/runs", "/api/v1/research/summary") and method == "GET":
            sid = self._cookie(env, "__Host-alpha_session")
            if not sid:
                return reply("401 Unauthorized")
            try:
                owner = self.sessions.resolve_owner(sid)
                if not isinstance(owner, str) or not re.fullmatch(r"oidc_[a-f0-9]{64}", owner):
                    raise PermissionError("unverified account")
                # A valid session is not proof that account access is still active.
                # No tenant credential lookup or data query may precede this check.
                if self.authorize_owner(owner) is not True:
                    raise PermissionError("account not authorised")
            except PermissionError:
                return reply("403 Forbidden")
            except Exception:
                return reply("503 Service Unavailable")
            try:
                if self.rate_limiter.allow_owner(owner) is not True:
                    return reply("503 Service Unavailable")
            except RateLimitExceeded:
                return reply("429 Too Many Requests")
            except Exception:
                return reply("503 Service Unavailable")
            try:
                data = self.reader.list_runs(owner) if path.endswith("/runs") else self.reader.summary(owner)
                body = json.dumps({"status": "verified_source", "data": data}, allow_nan=False).encode()
                return reply("200 OK", body, [("Content-Type", "application/json")])
            except PermissionError:
                return reply("403 Forbidden")
            except Exception:
                return reply("503 Service Unavailable")
        return reply("404 Not Found")

    @staticmethod
    def _clear_state():
        return "__Host-alpha_oauth_state=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0"

    @staticmethod
    def _cookie(env, name):
        try:
            header = env.get("HTTP_COOKIE", "")
            if len(header) > 4096 or header.count(name + "=") != 1:
                return None
            cookie = SimpleCookie()
            cookie.load(header)
            value = cookie[name].value if name in cookie else None
            return value if value and len(value) <= 512 else None
        except Exception:
            return None
