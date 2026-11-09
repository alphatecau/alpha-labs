"""Read-only session-authorised paper account status adapter.

Never trusts browser-supplied account, subject or issuer. Requires HTTPS ingress.
No order, broker or trading endpoints.
"""
import json
from http.cookies import SimpleCookie

from alpha_lab.research.oidc_durable_store import DurableOIDCStore
from alpha_lab.research.oidc_postgres_store import PostgresOIDCStore
from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.paper_ownership_registry import PaperOwnershipRegistry


class SessionPaperStatusWSGI:
    def __init__(self, *, sessions, accounts, ownership):
        if not isinstance(sessions, (DurableOIDCStore, PostgresOIDCStore)):
            raise ValueError("Durable verified session store required")
        if not isinstance(ownership, PaperOwnershipRegistry):
            raise ValueError("Verified ownership registry required")
        self.sessions, self.accounts, self.ownership = sessions, accounts, ownership

    def __call__(self, env, start_response):
        def reply(status, body):
            payload = json.dumps(body, sort_keys=True).encode()
            start_response(status, [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(payload))),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
                ("Referrer-Policy", "no-referrer")])
            return [payload]

        if env.get("PATH_INFO") != "/api/research/paper/session-status":
            return reply("404 Not Found", {"error": "not_found"})
        if env.get("REQUEST_METHOD") != "GET":
            return reply("405 Method Not Allowed", {"error": "read_only"})
        if env.get("QUERY_STRING"):
            return reply("400 Bad Request", {"error": "query_not_supported"})
        if env.get("wsgi.url_scheme") != "https":
            return reply("403 Forbidden", {"error": "https_required"})
        try:
            jar = SimpleCookie()
            jar.load(env.get("HTTP_COOKIE", ""))
            sid = jar["__Host-alpha_session"].value
            subject, issuer = self.sessions.authenticate(sid)
            principal = VerifiedPrincipal(subject=subject, issuer=issuer)
        except (KeyError, ValueError, TypeError, PermissionError):
            return reply("401 Unauthorized", {"error": "authentication_required"})
        try:
            self.ownership.require(principal, "primary")
            status = self.accounts.status(principal, "primary")
        except PermissionError:
            return reply("404 Not Found", {"error": "account_not_available"})
        except Exception:
            return reply("503 Service Unavailable", {"error": "status_unavailable"})
        return reply("200 OK", {"paper": status, "real_money": False,
                                "live_copy": "DISABLED_NOT_IMPLEMENTED"})
