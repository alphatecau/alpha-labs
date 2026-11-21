"""Research-only authenticated staging WSGI composition; never deploy without review.

All security-sensitive services are injected: verified OIDC controller, durable
session repository, per-tenant credential broker and read-only research reader.
No implicit environment or database fallback.
"""
import hmac
import json
import logging
import re
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlencode, urlsplit

from deployment.account_role_research_reader import AccountRoleResearchReader
from deployment import research_dashboard
from deployment.paper_site import PAPER_SITE, RelayBudget, callback_params, page_number, research_evidence
from deployment.auth0_pkce_callback import ResearchAccountNotProvisioned


class StagingResearchBFF:
    def __init__(self, flow, controller, sessions, reader, *, origin, authorize_owner, paper_reader=None,
                 market_reader=None, revision=None):
        parsed = urlsplit(origin)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("exact HTTPS origin required")
        if any(component is None for component in (flow, controller, sessions, reader)):
            raise ValueError("all authenticated dependencies required")
        if not callable(authorize_owner):
            raise ValueError("current ownership authorizer required")
        if not isinstance(reader, AccountRoleResearchReader):
            raise ValueError("tenant-role research reader required")
        self.flow, self.controller, self.sessions, self.reader = flow, controller, sessions, reader
        self.paper_reader = paper_reader
        self.market_reader = market_reader
        self.revision = revision
        self.paper_budget = RelayBudget()
        self.authorize_owner = authorize_owner
        self.origin = origin.rstrip("/")

    def __call__(self, env, start_response):
        def reply(status, data=b"", headers=(), *, html=False):
            form_destinations = "'self'"
            if html and isinstance(getattr(self.flow, "issuer", None), str):
                # Chrome can apply form-action to the redirect after a logout POST.
                provider = urlsplit(self.flow.issuer)
                if provider.scheme == "https" and provider.hostname and re.fullmatch(r"[A-Za-z0-9.-]+", provider.netloc):
                    form_destinations += " https://" + provider.netloc
            base = [("Content-Length", str(len(data))), ("Cache-Control", "no-store"),
                    ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"),
                    ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
                     "style-src 'self'; form-action " + form_destinations)]
            if html:
                base.append(("Content-Type", "text/html; charset=utf-8"))
            start_response(status, base + list(headers))
            return [data]

        def login_error(status, headers=()):
            if "text/html" in env.get("HTTP_ACCEPT", ""):
                return reply(status, research_dashboard.access_message(
                    "Sign-in could not be completed",
                    "Try signing in again with your provisioned research account."), headers, html=True)
            return reply(status, headers=headers)

        path, method = env.get("PATH_INFO", ""), env.get("REQUEST_METHOD", "")
        if path == "/dashboard.css" and method == "GET":
            return reply("200 OK", research_dashboard.CSS, [("Content-Type", "text/css; charset=utf-8")])
        if path == "/signed-out" and method == "GET":
            return reply("200 OK", research_dashboard.signed_out(), html=True)
        if path == "/healthz" and method == "GET":
            return reply("200 OK", b'{"status":"ok","trading":"disabled"}',
                         [("Content-Type", "application/json")])
        if path in ("/auth/login", "/site-relay/auth/login") and method == "GET":
            try:
                url = self.flow.begin(for_site=True) if path.startswith("/site-relay/") else self.flow.begin()
                params = parse_qs(urlsplit(url).query)
                state = params["state"][0]
            except Exception:
                return login_error("503 Service Unavailable")
            # Bind the single-use server-side state to the initiating browser.
            cookie = "__Host-alpha_oauth_state=" + state + "; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=300"
            return reply("302 Found", headers=[("Location", url), ("Set-Cookie", cookie)])
        if path in ("/auth/callback", "/site-relay/auth/callback") and method == "GET":
            params = callback_params(env.get("QUERY_STRING", ""))
            if (set(params) not in ({"code", "state"}, {"code", "state", "iss"}) or
                    any(len(v) != 1 for v in params.values()) or
                    ("iss" in params and params["iss"][0] != self.flow.issuer)):
                return login_error("401 Unauthorized")
            state_cookie = self._cookie(env, "__Host-alpha_oauth_state")
            state = params["state"][0]
            site_state = re.fullmatch(r"site\.[A-Za-z0-9_-]{43}", state) is not None
            if site_state and path == "/auth/callback":
                # Auth0 returns here using the existing registered redirect URI. Only the
                # initiating Site host holds the state cookie needed to finish this flow.
                return reply("303 See Other", headers=[("Location", PAPER_SITE + "/auth/callback?" +
                                         urlencode({k: v[0] for k, v in params.items()}))])
            if path.startswith("/site-relay/") and not site_state:
                return login_error("401 Unauthorized")
            if not state_cookie or not hmac.compare_digest(state_cookie.encode(), state.encode()):
                return login_error("401 Unauthorized")
            try:
                session_cookie = self.controller.complete(state, params["code"][0])
            except ResearchAccountNotProvisioned:
                headers = [("Set-Cookie", self._clear_state())]
                if "text/html" in env.get("HTTP_ACCEPT", ""):
                    return reply("403 Forbidden", research_dashboard.access_message(
                        "Research access required",
                        "Sign-in succeeded. Ask your administrator to provision your research account."),
                        headers, html=True)
                return reply("403 Forbidden", headers=headers)
            except Exception:
                return login_error("401 Unauthorized", headers=[("Set-Cookie", self._clear_state())])
            return reply("303 See Other", headers=[
                ("Location", PAPER_SITE + "/paper" if site_state else self.origin + "/"),
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
            headers = [("Set-Cookie", "__Host-alpha_session=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0")]
            if "text/html" in env.get("HTTP_ACCEPT", ""):
                # Revoke locally before ending the provider's SSO session.
                params = urlencode({"client_id": self.flow.client_id, "returnTo": self.origin + "/signed-out"})
                headers.append(("Location", self.flow.issuer + "v2/logout?" + params))
                return reply("303 See Other", headers=headers)
            return reply("204 No Content", headers=headers)
        page = path in ("/", "/dashboard")
        paper = path in ("/api/v1/paper/snapshot", "/api/v1/paper/markets", "/api/v1/paper/research", "/api/v1/paper/identity")
        if (page or paper or path in ("/api/v1/research/runs", "/api/v1/research/summary")) and method == "GET":
            sid = self._cookie(env, "__Host-alpha_session")
            if not sid:
                if page:
                    return reply("303 See Other", headers=[("Location", "/auth/login")])
                return reply("401 Unauthorized")
            stage = "session_lookup"
            try:
                owner = self.sessions.resolve_owner(sid)
                if not isinstance(owner, str) or not re.fullmatch(r"oidc_[a-f0-9]{64}", owner):
                    raise PermissionError("unverified account")
                # A valid session is not proof that account access is still active.
                # No tenant credential lookup or data query may precede this check.
                stage = "ownership_lookup"
                if self.authorize_owner(owner) is not True:
                    raise PermissionError("account not authorised")
                if paper:
                    stage = "paper_read"
                    if not self.paper_budget.allow(owner):
                        return reply("429 Too Many Requests", headers=[("Retry-After", "60")])
                    try:
                        index = page_number(env.get("QUERY_STRING", ""), path.endswith("/snapshot"))
                    except ValueError:
                        return reply("400 Bad Request")
                    if path.endswith("/identity"):
                        # Owner-only provisioning diagnostic; never returns credentials or session data.
                        data = {"owner": owner, "journal_provisioned": bool(
                            self.paper_reader is not None and owner in self.paper_reader.bindings)}
                    elif path.endswith("/snapshot"):
                        if self.paper_reader is None:
                            return reply("503 Service Unavailable")
                        data = self.paper_reader.snapshot(owner, page=index) if index else self.paper_reader.snapshot(owner)
                    elif path.endswith("/research"):
                        data = {**research_evidence(), "runs": self.reader.list_runs(owner)}
                    else:
                        if self.market_reader is None:
                            return reply("503 Service Unavailable")
                        data = self.market_reader()
                    body = json.dumps({"status": "verified_source", "mode": "paper_only", "trading": "disabled",
                                       "data": data}, allow_nan=False).encode()
                    headers = [("Content-Type", "application/json")]
                    if self.revision:
                        headers.append(("X-Alpha-Paper-Commit", self.revision))
                    return reply("200 OK", body, headers)
                stage = "research_read"
                if page:
                    return reply("200 OK", research_dashboard.dashboard(self.reader.list_runs(owner)), html=True)
                data = self.reader.list_runs(owner) if path.endswith("/runs") else self.reader.summary(owner)
                body = json.dumps({"status": "verified_source", "data": data}, allow_nan=False).encode()
                return reply("200 OK", body, [("Content-Type", "application/json")])
            except PermissionError:
                if paper and stage == "session_lookup":
                    return reply("401 Unauthorized")
                logging.getLogger(__name__).warning("research_access_denied stage=%s", stage)
                if page:
                    return reply("403 Forbidden", research_dashboard.access_message(
                        "Access unavailable", "Sign in with a provisioned research account."), html=True)
                return reply("403 Forbidden")
            except Exception as exc:
                # Database exception messages can contain connection details. Log only categories.
                logging.getLogger(__name__).error("research_unavailable stage=%s type=%s sqlstate=%s",
                    stage, type(exc).__name__, getattr(exc, "sqlstate", None))
                if page:
                    return reply("503 Service Unavailable", research_dashboard.access_message(
                        "Research temporarily unavailable", "Your account data could not be verified."), html=True)
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
