"""Read-only WSGI adapter for offline paper-account status.

Not a production web server. Requires trusted server-owned account registry,
a configured token verifier and HTTPS at the upstream ingress. No trade routes.
"""
import json
from datetime import datetime, timezone
from urllib.parse import parse_qs

from alpha_lab.research.paper_identity import PaperIdentityVerifier


class PaperStatusWSGI:
    def __init__(self, *, verifier: PaperIdentityVerifier, accounts, now=None):
        if not isinstance(verifier, PaperIdentityVerifier):
            raise ValueError("A verified identity provider is required")
        self.verifier = verifier
        self.accounts = accounts
        self.now = now if now is not None else lambda: datetime.now(timezone.utc)

    def __call__(self, environ, start_response):
        def reply(status, payload):
            data = json.dumps(payload, sort_keys=True).encode("utf-8")
            start_response(status, [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(data))),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
                ("Referrer-Policy", "no-referrer"),
            ])
            return [data]

        # Strictly one supported route; never permit writes or account creation.
        if environ.get("PATH_INFO") != "/api/research/paper/status":
            return reply("404 Not Found", {"error": "not_found"})
        if environ.get("REQUEST_METHOD") != "GET":
            return reply("405 Method Not Allowed", {"error": "read_only"})
        if environ.get("QUERY_STRING"):
            return reply("400 Bad Request", {"error": "query_not_supported"})
        header = environ.get("HTTP_AUTHORIZATION", "")
        if not isinstance(header, str) or not header.startswith("Bearer "):
            return reply("401 Unauthorized", {"error": "authentication_required"})
        try:
            principal = self.verifier.verify(header[7:], now=self.now())
        except (PermissionError, ValueError, UnicodeError):
            return reply("401 Unauthorized", {"error": "authentication_failed"})
        try:
            # Account alias is fixed by the server; no user/account identifier
            # can be supplied in the URL, headers or request JSON.
            status = self.accounts.status(principal, "primary")
        except PermissionError:
            return reply("404 Not Found", {"error": "account_not_available"})
        except Exception:
            return reply("503 Service Unavailable", {"error": "status_unavailable"})
        return reply("200 OK", {"paper": status, "real_money": False,
                                "live_copy": "DISABLED_NOT_IMPLEMENTED"})
