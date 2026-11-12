"""Research-only external BFF WSGI adapter.

Run only behind a separately verified HTTPS ingress. Session verification,
ownership, rate limits, and outbound fixed-origin TLS transport are injected.
No Auth0 callback, database access, or trade execution is implemented here.
"""
import json
from alpha_lab.research.postgres_paper_security import RateLimitExceeded, RateLimitUnavailable
from deployment.bff_session_bridge import SessionOwnershipVerifier
from deployment.trusted_site_relay import TrustedSiteRelay


class ResearchDashboardBFF:
    def __init__(self, *, relay):
        if not isinstance(relay, TrustedSiteRelay) or not isinstance(relay.verify_session, SessionOwnershipVerifier):
            raise ValueError("trusted relay with a shared-limited session verifier required")
        self.relay = relay

    def __call__(self, env, start_response):
        def reply(status, payload):
            data = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
            start_response(status, [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(data))),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
                ("Referrer-Policy", "no-referrer"),
                ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"),
            ])
            return [data]

        if env.get("wsgi.url_scheme") != "https":
            return reply("403 Forbidden", {"error": "https_required"})
        if env.get("REQUEST_METHOD") != "GET":
            return reply("405 Method Not Allowed", {"error": "read_only"})
        if env.get("QUERY_STRING"):
            return reply("400 Bad Request", {"error": "query_not_supported"})
        resource = {
            "/api/research/runs": "runs",
            "/api/research/summary": "summary",
        }.get(env.get("PATH_INFO"))
        if resource is None:
            return reply("404 Not Found", {"error": "unavailable"})
        try:
            result = self.relay.fetch(env.get("HTTP_COOKIE", ""), resource)
        except RateLimitExceeded:
            return reply("429 Too Many Requests", {"error": "rate_limited"})
        except RateLimitUnavailable:
            return reply("503 Service Unavailable", {"error": "research_unavailable"})
        except PermissionError:
            return reply("401 Unauthorized", {"error": "authentication_required"})
        except Exception:
            return reply("503 Service Unavailable", {"error": "research_unavailable"})
        return reply("200 OK", result)
