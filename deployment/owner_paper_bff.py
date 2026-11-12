"""Opt-in owner paper composition. No listener, deployment or default credentials.

Reuse the authenticated research BFF and its durable identity/shared quota. The
old HMAC-only relay is not mounted. Operators must independently verify the
Auth0/proxy/storage/checkpoint deployment gates before serving this factory.
"""
import hashlib
import hmac
import json
import re
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit

from alpha_lab.research.live_paper_api import ROUTES, _json_object, _read_body
from alpha_lab.research.live_paper_session import LivePaperSession, PaperRejection
from alpha_lab.research.postgres_paper_security import RateLimitExceeded
from deployment.staging_authenticated_bff import StagingResearchBFF
from deployment.postgres_paper_checkpoints import PostgresPaperCheckpoints
from deployment.verified_proxy_ingress import VerifiedProxyIngress

_ASSETS = {"/owner-paper/": ("index.html", "text/html; charset=utf-8"),
           "/owner-paper/paper.css": ("paper.css", "text/css; charset=utf-8"),
           "/owner-paper/paper.js": ("paper.js", "text/javascript; charset=utf-8")}
_ROOT = Path(__file__).resolve().parents[1] / "apps/sites/owner-paper"
_STATUS = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
           404: "Not Found", 405: "Method Not Allowed", 409: "Conflict",
           429: "Too Many Requests", 503: "Service Unavailable"}


class OwnerPaperBFF:
    def __init__(self, research, paper, *, owner_id, csrf_key):
        if (not isinstance(research, StagingResearchBFF)
                or not isinstance(paper, LivePaperSession)
                or not isinstance(owner_id, str) or not re.fullmatch(r"oidc_[a-f0-9]{64}", owner_id)
                or not isinstance(csrf_key, bytes) or len(csrf_key) < 32):
            raise ValueError("verified research boundary, owner paper binding and CSRF key required")
        p = urlsplit(research.origin)
        if (p.scheme != "https" or not p.hostname or p.username or p.password
                or p.path or p.query or p.fragment):
            raise ValueError("canonical HTTPS origin required")
        if paper._guard()["account"] != owner_id:
            raise ValueError("paper journal must be bound to the pinned internal owner")
        if (not isinstance(paper.checkpoint_store, PostgresPaperCheckpoints)
                or paper.checkpoint_store.owner_id != owner_id
                or paper.checkpoint_store.ready() is not True):
            raise ValueError("separate protected checkpoint authority required for owner API")
        self.research, self.paper, self.owner_id = research, paper, owner_id
        self.csrf_key = csrf_key
        self.lock = RLock()
        self._armed_sid = None

    def _csrf(self, sid):
        message = ("owner-paper-v1\0" + self.owner_id + "\0" + sid).encode()
        return hmac.new(self.csrf_key, message, hashlib.sha256).hexdigest()

    def _halt(self, *, fault=False):
        self._armed_sid = None
        try:
            if fault:
                self.paper.fail_closed()
                return False
            else:
                self.paper.control("halt")
                return True
        except Exception:
            self.paper.fail_closed()
            return False

    def on_market_update(self):
        """Health watchdog also checks the session that armed this paper process."""
        with self.lock:
            if self._armed_sid is not None:
                try:
                    owner = self.research.sessions.resolve_owner(self._armed_sid)
                    if owner != self.owner_id or self.research.authorize_owner(owner) is not True:
                        raise PermissionError("paper authority revoked")
                    if self.research.rate_limiter.ready() is not True:
                        raise RuntimeError("shared quota dependency unavailable")
                except PermissionError:
                    self._halt()
                except Exception:
                    self._halt(fault=True)
            self.paper.on_market_update()

    @staticmethod
    def _reply(respond, code, payload, content_type="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(
            payload, separators=(",", ":"), allow_nan=False).encode()
        respond(f"{code} {_STATUS[code]}", [
            ("Content-Type", content_type), ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer"),
            ("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; "
             "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"),
        ])
        return [body]

    def __call__(self, env, respond):
        path, method = env.get("PATH_INFO", ""), env.get("REQUEST_METHOD", "")
        if path not in ROUTES and path not in _ASSETS:
            # Never expose alternate paper aliases or the legacy relay factory.
            if path.startswith(("/api/v1/paper", "/api/paper", "/owner-paper")):
                return self._reply(respond, 404, {"error": "NOT_FOUND"})
            result = self.research(env, respond)
            if path == "/auth/logout" and method == "POST":
                self.on_market_update()
            return result
        if env.get("QUERY_STRING"):
            return self._reply(respond, 400, {"error": "QUERY_FORBIDDEN"})
        if method != (ROUTES[path] if path in ROUTES else "GET"):
            return self._reply(respond, 405, {"error": "METHOD_NOT_ALLOWED"})
        sid = self.research._cookie(env, "__Host-alpha_session")
        if not sid:
            return self._reply(respond, 401, {"error": "AUTHENTICATION_REQUIRED"})
        with self.lock:
            try:
                owner = self.research.sessions.resolve_owner(sid)
                if owner != self.owner_id:
                    raise PermissionError("owner-only paper account")
                if self.research.authorize_owner(owner) is not True:
                    raise PermissionError("current ownership required")
            except PermissionError:
                if sid == self._armed_sid:
                    self._halt()
                return self._reply(respond, 403, {"error": "OWNER_REQUIRED"})
            except Exception:
                self._halt(fault=True)
                return self._reply(respond, 503, {"error": "IDENTITY_UNAVAILABLE"})
            try:
                if path in _ASSETS:
                    name, kind = _ASSETS[path]
                    data = (_ROOT / name).read_bytes()
                    if name == "index.html":
                        data = data.replace(b"{{csrf}}", self._csrf(sid).encode())
                    return self._reply(respond, 200, data, kind)
                payload = None
                if method == "POST":
                    token = env.get("HTTP_X_ALPHA_CSRF", "")
                    if (env.get("HTTP_ORIGIN") != self.research.origin
                            or not isinstance(token, str) or not re.fullmatch(r"[a-f0-9]{64}", token)
                            or not hmac.compare_digest(token, self._csrf(sid))):
                        return self._reply(respond, 403, {"error": "CSRF_REJECTED"})
                    try:
                        payload = json.loads(_read_body(env, method), object_pairs_hook=_json_object)
                    except (ValueError, RecursionError):
                        return self._reply(respond, 400, {"error": "INVALID_JSON"})
                elif _read_body(env, method):
                    return self._reply(respond, 400, {"error": "INVALID_REQUEST"})
                # Authenticated emergency HALT remains available at an exhausted
                # quota. It returns no portfolio/history and cannot submit orders.
                if path.endswith("/control") and payload == {"action": "halt"}:
                    if not self._halt():
                        return self._reply(respond, 503, {"error": "HALT_PERSISTENCE_UNAVAILABLE"})
                    return self._reply(respond, 200, {"mode": "SIMULATION_ONLY", "armed": False})
                try:
                    if self.research.rate_limiter.allow_owner(owner) is not True:
                        raise RuntimeError("shared quota unavailable")
                except RateLimitExceeded:
                    return self._reply(respond, 429, {"error": "RATE_LIMITED"})
                self.on_market_update()
                if method == "GET":
                    data = self.paper.state()
                elif path.endswith("/orders"):
                    data = self.paper.order(payload)
                elif (isinstance(payload, dict) and set(payload) == {"action", "revision"}
                      and payload["action"] == "arm" and type(payload["revision"]) is int
                      and payload["revision"] >= 0):
                    data = self.paper.control("arm", expected_revision=payload["revision"])
                    self._armed_sid = sid
                else:
                    return self._reply(respond, 400, {"error": "INVALID_CONTROL"})
                return self._reply(respond, 200, {**data, "mode": "SIMULATION_ONLY"})
            except PaperRejection as exc:
                return self._reply(respond, exc.status, {"error": exc.code})
            except Exception:
                self._halt(fault=True)
                return self._reply(respond, 503, {"error": "PAPER_HALTED"})


def create_owner_paper_application(*, research, paper, owner_id, csrf_key, trusted_peer_cidrs):
    """Explicit operator composition only; no environment-based default app.

    Start the read-only market feed and authority watchdog only when this factory
    is deliberately invoked. No broker execution adapter exists in this path.
    The returned WSGI wrapper must never be reachable except through its verified
    proxy peer ranges. Shutdown must stop the feed before closing the journal.
    """
    app = OwnerPaperBFF(research, paper, owner_id=owner_id, csrf_key=csrf_key)
    ingress = VerifiedProxyIngress(app, research.origin, trusted_peer_cidrs=trusted_peer_cidrs)
    paper.feed.start(app.on_market_update)
    return ingress
