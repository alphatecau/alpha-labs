"""Research-only authenticated staging WSGI entry.

Use an approved operator composition to inject independently reviewed dependencies.
No environment-selected Python imports, default credentials, migrations or listeners.
The factory can be served by a production WSGI server only after approval.
"""
import json
from deployment.authenticated_staging_bootstrap import build_authenticated_application
from deployment.verified_proxy_ingress import VerifiedProxyIngress


def create_application(*, environ, ownership, principal_factory, state_connect,
                       session_connect, tenant_connect, trusted_peer_cidrs,
                       readiness_check, verifier_factory=None):
    """Build an authenticated, proxy-guarded app or fail startup."""
    if not callable(readiness_check):
        raise ValueError("independent dependency readiness check required")
    if not isinstance(environ, dict):
        raise ValueError("explicit trusted environment required")
    if not trusted_peer_cidrs:
        raise ValueError("verified proxy peer ranges required")
    if verifier_factory is None:
        from deployment.auth0_refreshing_verifier import RefreshingAuth0Verifier
        verifier_factory = RefreshingAuth0Verifier
    app = build_authenticated_application(
        environ=environ, ownership=ownership, principal_factory=principal_factory,
        state_connect=state_connect, session_connect=session_connect,
        tenant_connect=tenant_connect, verifier_factory=verifier_factory)
    # Constructing the wrapper validates the peer CIDRs and HTTPS origin.
    guarded = VerifiedProxyIngress(app, environ["ALPHA_BFF_ORIGIN"],
                                   trusted_peer_cidrs=trusted_peer_cidrs)

    def application(request, start_response):
        # The readiness endpoint is guarded by the same proxy boundary.
        def route(env, respond):
            path = env.get("PATH_INFO", "")
            method = env.get("REQUEST_METHOD", "")
            if path == "/livez" and method == "GET":
                return _reply(respond, "200 OK", {"status": "alive", "authenticated_ready": False})
            if path == "/readyz" and method == "GET":
                try:
                    ready = readiness_check()
                    if ready is not True:
                        raise RuntimeError("dependencies unavailable")
                except Exception:
                    return _reply(respond, "503 Service Unavailable",
                                  {"status": "unavailable", "authenticated_ready": False})
                return _reply(respond, "200 OK",
                              {"status": "ready", "authenticated_ready": True})
            return app(env, respond)
        # Preserve VerifiedProxyIngress validation for every request.
        return VerifiedProxyIngress(route, environ["ALPHA_BFF_ORIGIN"],
                                    trusted_peer_cidrs=trusted_peer_cidrs)(request, start_response)
    return application


def _reply(start_response, status, payload):
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    start_response(status, [("Content-Type", "application/json"),
                            ("Content-Length", str(len(data))),
                            ("Cache-Control", "no-store"),
                            ("X-Content-Type-Options", "nosniff")])
    return [data]


# Deliberately no module-level application or executable server.
# An independently reviewed operator composition must supply all bindings.
