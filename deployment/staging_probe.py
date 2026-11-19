"""Read-only staging entry point for public, versioned Alpha Labs research."""

import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from wsgiref.simple_server import make_server

RESULTS_PATH = "/api/v1/research/results"
AUDIT = Path(__file__).resolve().parents[1] / "docs/evidence/2026-11-05_REPRODUCTION_AUDIT.json"
AUDIT_SHA256 = "e1f03b0caf41e86d90ba582465ab038a93ce9be09669adce3b4fac8692c3e06f"


def application(environ, start_response):
    def reply(status, payload, extra=()):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        start_response(status, [
            ("Content-Type", "application/json"), ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"), *extra,
        ])
        return [body]

    path = environ.get("PATH_INFO")
    method = environ.get("REQUEST_METHOD")
    if path == "/healthz" and method == "GET":
        return reply("200 OK", {"status": "ok", "mode": "research_only", "trading": "disabled"})
    if path != RESULTS_PATH or environ.get("QUERY_STRING"):
        return reply("404 Not Found", {"error": "unavailable"})
    if method != "GET":
        return reply("405 Method Not Allowed", {"error": "method_not_allowed"}, [("Allow", "GET")])

    token = os.environ.get("ALPHA_RESEARCH_TOKEN", "")
    commit = os.environ.get("RENDER_GIT_COMMIT", "")
    if not re.fullmatch("[a-f0-9]{64}", token) or not re.fullmatch("[a-f0-9]{40}", commit):
        return reply("503 Service Unavailable", {"error": "research_unconfigured"})
    supplied = environ.get("HTTP_AUTHORIZATION", "").encode()
    if not hmac.compare_digest(supplied, f"Bearer {token}".encode()):
        return reply("401 Unauthorized", {"error": "unauthorised"}, [("WWW-Authenticate", "Bearer")])

    try:
        evidence = AUDIT.read_bytes()
    except OSError:
        return reply("503 Service Unavailable", {"error": "evidence_unavailable"})
    if hashlib.sha256(evidence).hexdigest() != AUDIT_SHA256:
        return reply("503 Service Unavailable", {"error": "evidence_unverified"})
    return reply("200 OK", evidence, [
        ("X-Alpha-Research-Commit", commit), ("X-Alpha-Evidence-SHA256", AUDIT_SHA256),
    ])


if __name__ == "__main__":
    # Render requires a wildcard listener behind its TLS ingress. Local runs use loopback.
    host = "0.0.0.0" if os.environ.get("RENDER") == "true" else "127.0.0.1"  # nosec B104
    with make_server(host, int(os.environ.get("PORT", "10000")), application) as server:
        print(f"Research HTTP port {server.server_port}", flush=True)
        server.serve_forever()
