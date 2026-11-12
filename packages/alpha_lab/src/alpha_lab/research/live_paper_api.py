"""Authenticated WSGI entry point for the single-owner paper service."""
import atexit
import hmac
import json
import os
import re
import time
from hashlib import sha256

from alpha_lab.research.live_paper_session import LivePaperSession, PaperRejection
from alpha_lab.research.paper_market_feed import PaperMarketFeed

PREFIX = "/api/v1/paper"
ROUTES = {f"{PREFIX}/state": "GET", f"{PREFIX}/orders": "POST", f"{PREFIX}/control": "POST"}
_MAX_BODY = 2048
_MAX_RELAY_AGE = 30
_SHA = re.compile(r"[a-f0-9]{40}")
_NONCE = re.compile(r"[a-f0-9]{32}")
_SECRET = re.compile(r"[a-f0-9]{64}")
_ACCOUNT = re.compile(r"[A-Za-z0-9_-]{16,80}")
_HTTP = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found",
         405: "Method Not Allowed", 409: "Conflict", 429: "Too Many Requests", 503: "Service Unavailable"}


def relay_message(method, path, commit, account, stamp, nonce, body):
    return "\n".join(("alpha-paper-relay-v1", method, path, commit, account,
                      stamp, nonce, sha256(body).hexdigest())).encode()


def _read_body(env, method):
    length = env.get("CONTENT_LENGTH", "")
    if method == "GET" and length in ("", "0"):
        return b""
    content_type = env.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower()
    if (method != "POST" or content_type != "application/json"
            or not re.fullmatch(r"[0-9]{1,4}", length) or not 0 < int(length) <= _MAX_BODY):
        raise PaperRejection("INVALID_REQUEST", "Expected a bounded JSON body", 400)
    body = env["wsgi.input"].read(int(length))
    if len(body) != int(length):
        raise PaperRejection("INVALID_REQUEST", "Incomplete request body", 400)
    return body


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


class LivePaperAPI:
    def __init__(self, session, *, account, key, commit, wall_clock=time.time):
        if not _SHA.fullmatch(commit) or not _ACCOUNT.fullmatch(account) or len(key) != 32:
            raise ValueError("relay key, account and pinned commit are required")
        self.session, self.account, self.key, self.commit = session, account, key, commit
        self.wall_clock = wall_clock

    def _authenticate(self, env, method, path, body):
        supplied_account = env.get("HTTP_X_ALPHA_PAPER_ACCOUNT", "")
        stamp = env.get("HTTP_X_ALPHA_PAPER_TIME", "")
        nonce = env.get("HTTP_X_ALPHA_PAPER_NONCE", "")
        mac = env.get("HTTP_X_ALPHA_PAPER_SIGNATURE", "")
        now = int(self.wall_clock())
        if (not _ACCOUNT.fullmatch(supplied_account) or not hmac.compare_digest(supplied_account, self.account)
                or not re.fullmatch(r"[0-9]{10}", stamp) or not 0 <= now - int(stamp) <= _MAX_RELAY_AGE
                or not _NONCE.fullmatch(nonce) or not _SECRET.fullmatch(mac)):
            raise PaperRejection("INVALID_RELAY", "Authenticated paper relay required", 401)
        message = relay_message(method, path, self.commit, self.account, stamp, nonce, body)
        expected = hmac.new(self.key, message, sha256).hexdigest()
        if not hmac.compare_digest(mac, expected):
            raise PaperRejection("INVALID_RELAY", "Authenticated paper relay required", 401)
        return nonce, now

    def __call__(self, env, start_response):
        def reply(status, payload):
            body = json.dumps(payload, allow_nan=False, separators=(",", ":")).encode()
            start_response(f"{status} {_HTTP[status]}", [
                ("Content-Type", "application/json"), ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                ("X-Alpha-Paper-Commit", self.commit),
            ])
            return [body]

        method, path = env.get("REQUEST_METHOD", ""), env.get("PATH_INFO", "")
        if path == "/healthz" and method == "GET":
            return reply(200, {"status": "ok", "mode": "research_only", "trading": "disabled", "commit": self.commit})
        if path not in ROUTES or env.get("QUERY_STRING"):
            return reply(404, {"error": "NOT_FOUND"})
        if method != ROUTES[path]:
            return reply(405, {"error": "METHOD_NOT_ALLOWED"})
        try:
            body = _read_body(env, method)
            nonce, now = self._authenticate(env, method, path, body)
        except PaperRejection as exc:
            return reply(exc.status, {"error": exc.code, "message": str(exc)})
        except (OSError, ValueError):
            return reply(400, {"error": "INVALID_REQUEST"})
        try:
            self.session.claim_request(nonce, now)
            if method == "GET":
                data = self.session.state()
            else:
                try:
                    payload = json.loads(body, object_pairs_hook=_json_object)
                except (ValueError, RecursionError):
                    return reply(400, {"error": "INVALID_JSON", "message": "Invalid JSON object"})
                if path.endswith("/orders"):
                    data = self.session.order(payload)
                else:
                    if payload == {"action": "halt"}:
                        data = self.session.control("halt")
                    elif (isinstance(payload, dict) and set(payload) == {"action", "revision"}
                          and payload["action"] == "arm" and type(payload["revision"]) is int
                          and payload["revision"] >= 0):
                        data = self.session.control("arm", expected_revision=payload["revision"])
                    else:
                        return reply(400, {"error": "INVALID_CONTROL", "message": "Invalid paper control action"})
            return reply(200, {**data, "mode": "SIMULATION_ONLY", "commit": self.commit})
        except PaperRejection as exc:
            return reply(exc.status, {"error": exc.code, "message": str(exc)})
        except Exception:
            self.session.fail_closed()
            return reply(503, {"error": "LEDGER_HALT", "message": "Paper service requires recovery"})


def create_app():
    """Render factory. Requires a mounted disk, an owner binding and an exact build SHA."""
    directory = os.environ["ALPHA_PAPER_DATA_DIR"]
    account = os.environ["ALPHA_PAPER_ACCOUNT_ID"]
    key_hex = os.environ["ALPHA_PAPER_RELAY_KEY_HEX"]
    commit = os.environ["RENDER_GIT_COMMIT"]
    if not os.path.ismount(directory):
        raise RuntimeError("paper service requires a persistent mount")
    if not _SECRET.fullmatch(key_hex) or not _SHA.fullmatch(commit):
        raise RuntimeError("valid relay key and exact Render commit required")
    feed = PaperMarketFeed()
    session = LivePaperSession(directory, account, feed)
    app = LivePaperAPI(session, account=account, key=bytes.fromhex(key_hex), commit=commit)
    feed.start(session.on_market_update)

    def close():
        feed.close()
        session.close()

    atexit.register(close)
    return app
