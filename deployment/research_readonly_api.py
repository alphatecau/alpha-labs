"""Research-only WSGI API. Trusted server-side relay ONLY; no browser credentials.

Authentication is HMAC-SHA256 signed owner-bound short-lived relay assertions.
Data source must be an injected read-only query adapter; no fabricated results.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import time
from urllib.parse import parse_qs
from deployment.account_role_research_reader import AccountRoleResearchReader

def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def sign_assertion(owner, secret, *, now=None, ttl=60):
    """For trusted relay tests; NEVER expose signing secret to browser."""
    if not isinstance(owner, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", owner):
        raise ValueError("invalid owner")
    if not isinstance(secret, str) or len(secret) < 32:
        raise ValueError("strong relay signing secret required")
    if not isinstance(ttl, int) or not 1 <= ttl <= 120:
        raise ValueError("invalid ttl")
    now = int(time.time() if now is None else now)
    payload = _b64(json.dumps({"sub": owner, "iat": now, "exp": now + ttl, "aud": "alpha-labs-readonly-v1"}, separators=(",", ":"), sort_keys=True).encode())
    signature = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return payload + "." + signature

def verify_assertion(value, secret, *, now=None):
    if (not isinstance(value, str) or len(value) > 1024
            or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]{43}", value)):
        raise PermissionError("invalid assertion")
    if not isinstance(secret, str) or len(secret) < 32:
        raise PermissionError("relay not configured")
    payload, signature = value.split(".")
    expected = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise PermissionError("invalid signature")
    try:
        raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        claims = json.loads(raw)
        now = int(time.time() if now is None else now)
        if claims.get("aud") != "alpha-labs-readonly-v1" or not isinstance(claims.get("sub"), str):
            raise ValueError()
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", claims["sub"]):
            raise ValueError()
        if type(claims.get("iat")) is not int or type(claims.get("exp")) is not int:
            raise ValueError()
        if not (now - 30 <= claims["iat"] <= now and now < claims["exp"] <= claims["iat"] + 120):
            raise ValueError()
        return claims["sub"]
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise PermissionError("expired or malformed assertion") from exc

class ResearchReadOnlyAPI:
    def __init__(self, reader=None, secret=None, clock=None):
        if reader is not None and not isinstance(reader, AccountRoleResearchReader):
            raise ValueError("tenant-role research reader required")
        self.reader = reader
        self.secret = secret
        self.clock = clock or time.time

    def __call__(self, environ, start_response):
        def respond(status, payload):
            body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
            start_response(status, [("Content-Type", "application/json"), ("Content-Length", str(len(body))),
                                    ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                                    ("Referrer-Policy", "no-referrer"), ("Access-Control-Allow-Origin", "null")])
            return [body]
        path = environ.get("PATH_INFO", "")
        method = environ.get("REQUEST_METHOD", "")
        if path == "/healthz" and method == "GET":
            return respond("200 OK", {"status": "ok", "mode": "read_only", "trading": "disabled"})
        if method != "GET":
            return respond("405 Method Not Allowed", {"error": "read_only"})
        if path not in ("/api/v1/research/runs", "/api/v1/research/summary"):
            return respond("404 Not Found", {"error": "unavailable"})
        authorization = environ.get("HTTP_AUTHORIZATION", "")
        if not authorization.startswith("Bearer "):
            return respond("401 Unauthorized", {"error": "unauthorised"})
        try:
            owner = verify_assertion(authorization[7:], self.secret, now=int(self.clock()))
        except PermissionError:
            return respond("401 Unauthorized", {"error": "unauthorised"})
        if self.reader is None:
            return respond("503 Service Unavailable", {"error": "data_unavailable"})
        try:
            if path.endswith("/runs"):
                result = self.reader.list_runs(owner, limit=50)
            else:
                result = self.reader.summary(owner)
            return respond("200 OK", {"status": "verified_source", "data": result})
        except Exception:
            return respond("503 Service Unavailable", {"error": "data_unavailable"})

application = ResearchReadOnlyAPI()
if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    with make_server("127.0.0.1", int(os.environ.get("PORT", "10000")), application) as server:
        server.serve_forever()
