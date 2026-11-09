"""Research-only authenticated read-only API composition.

All dependencies are injected. No credentials, database provisioning or network
listeners. The deployed health-only probe is deliberately unaffected.
"""
import json
from alpha_lab.research.oidc_browser_wsgi import OIDCBrowserWSGI
from alpha_lab.research.session_paper_status_wsgi import SessionPaperStatusWSGI
from alpha_lab.research.oidc_postgres_store import PostgresOIDCStore
from alpha_lab.research.postgres_paper_security import PostgresPaperOwnership, PostgresIdentityLimiter
from alpha_lab.research.trusted_proxy_boundary import canonicalise_verified_peer


class AuthenticatedReadOnlyStaging:
    def __init__(self, *, auth, sessions, accounts, ownership, limiter,
                 expected_origin, trusted_peer_cidrs):
        if not isinstance(auth, OIDCBrowserWSGI) or not isinstance(sessions, PostgresOIDCStore):
            raise ValueError("Verified OIDC and PostgreSQL sessions required")
        if auth.store is not sessions or not isinstance(ownership, PostgresPaperOwnership) or not isinstance(limiter, PostgresIdentityLimiter):
            raise ValueError("Shared PostgreSQL security components required")
        if not isinstance(trusted_peer_cidrs, (tuple, list)) or not trusted_peer_cidrs:
            raise ValueError("Explicit trusted ingress peer configuration required")
        if auth.origin != expected_origin:
            raise ValueError("OIDC callback and ingress origin must match")
        self.auth = auth
        self.paper = SessionPaperStatusWSGI(sessions=sessions, accounts=accounts,
                                           ownership=ownership, limiter=limiter)
        self.expected_origin = expected_origin
        self.trusted_peer_cidrs = tuple(trusted_peer_cidrs)

    def __call__(self, environ, start_response):
        def denied(status, error):
            body = json.dumps({"error": error}).encode()
            start_response(status, [("Content-Type", "application/json"),
                                    ("Content-Length", str(len(body))),
                                    ("Cache-Control", "no-store")])
            return [body]
        try:
            env = canonicalise_verified_peer(
                environ, trusted_peer_cidrs=self.trusted_peer_cidrs,
                expected_origin=self.expected_origin)
        except (ValueError, PermissionError, TypeError):
            return denied("403 Forbidden", "ingress_rejected")
        path = env.get("PATH_INFO", "")
        if path in ("/auth/login", "/auth/callback", "/auth/me", "/auth/logout"):
            return self.auth(env, start_response)
        if path == "/api/research/paper/session-status":
            return self.paper(env, start_response)
        return denied("404 Not Found", "not_found")
