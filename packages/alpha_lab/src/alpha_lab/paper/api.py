"""Loopback-only development API and dashboard; no public hosting or broker API.

Opaque short-lived operator tokens are checked before tenant-scoped access.
No arbitrary tenant/user header, query string or agent output establishes identity.
"""
from __future__ import annotations

from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

from . import VERSION
from .analytics import describe
from .committee import FIXTURE_STRATEGY, REJECTED
from .contracts import (ContractError, Forbidden, Proposal, Quote, canonical, timestamp)
from .ledger import reconcile
from .market_data import synthetic_quote

MAX_BODY_BYTES = 32_768
ROOT = Path(__file__).resolve().parents[5] / "apps/dashboard/paper"


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ContractError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ContractError("nonfinite JSON")))


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, engine, identity, *, dashboard_root=ROOT):
        if address[0] != "127.0.0.1":
            raise ValueError("development server must bind to IPv4 loopback")
        self.engine, self.identity, self.dashboard_root = engine, identity, Path(dashboard_root)
        self._rates, self._rate_lock = {}, threading.Lock()
        super().__init__(address, Handler)

    def rate_limit(self, key, *, limit=60):
        now = time.monotonic()
        with self._rate_lock:
            # Expire buckets to bound memory even for invalid random credentials.
            if len(self._rates) > 1000:
                self._rates = {k: v for k, v in self._rates.items() if now-v[0] < 60}
            start, count = self._rates.get(key, (now, 0))
            if now-start >= 60:
                start, count = now, 0
            self._rates[key] = (start, count+1)
            return count < limit


class Handler(BaseHTTPRequestHandler):
    server: LocalServer
    protocol_version = "HTTP/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(3)

    def log_message(self, format, *args):
        # Requests/tokens/account paths are deliberately omitted from terminal logs.
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; "
                         "script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; "
                         "base-uri 'none'; form-action 'self'")
        super().end_headers()

    def send_json(self, status, value):
        data = canonical(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if status == 429:
            self.send_header("Retry-After", "60")
        self.end_headers()
        self.wfile.write(data)

    def _boundary(self):
        authority = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != authority:
            raise Forbidden("invalid host")
        origin = self.headers.get("Origin")
        if origin is not None and origin != "http://"+authority:
            raise Forbidden("invalid origin")
        if (any(k.lower() in {"x-user-id", "x-tenant-id", "x-role", "x-forwarded-user"} for k in self.headers)
                or self.headers.get("Sec-Fetch-Site") == "cross-site"):
            raise Forbidden("untrusted identity or cross-site request")

    def _principal(self):
        value = self.headers.get("Authorization", "")
        if not value.startswith("Bearer "):
            raise Forbidden("credentials required")
        principal = self.server.identity.authenticate(value[7:])
        if not self.server.rate_limit((principal.tenant, principal.subject)):
            return None
        return principal

    def _body(self):
        if self.headers.get("Transfer-Encoding") is not None:
            raise ContractError("transfer encoding unsupported")
        size = self.headers.get("Content-Length")
        if size is None or not size.isdecimal() or not 0 < int(size) <= MAX_BODY_BYTES:
            raise ContractError("invalid body length")
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise ContractError("JSON content type required")
        value = strict_json(self.rfile.read(int(size)).decode("utf-8"))
        if type(value) is not dict:
            raise ContractError("JSON object required")
        return value

    def _handle(self, *, post=False):
        try:
            self._boundary()
            if not self.server.rate_limit("loopback", limit=600):
                self.send_json(429, {"status": "rate_limited"})
                return
            parsed = urlsplit(self.path)
            if parsed.query or parsed.fragment:
                raise ContractError("query parameters unsupported")
            path = parsed.path
            if path == "/api/v1/health" and not post:
                self.send_json(200, dict(version=VERSION, status="local_simulation_only",
                                         live_trading_enabled=False, production_deployment_enabled=False))
                return
            if not path.startswith("/api/") and not post:
                files = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                         "/style.css": ("style.css", "text/css")}
                if path not in files:
                    self.send_json(404, {"status": "not_found"})
                    return
                name, content_type = files[path]
                raw = (self.server.dashboard_root/name).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type+"; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            principal = self._principal()
            if principal is None:
                self.send_json(429, {"status": "rate_limited"})
                return
            if path == "/api/v1/signout" and post:
                if self._body() != {}:
                    raise ContractError("empty signout body required")
                self.server.identity.revoke(self.headers["Authorization"][7:])
                self.send_json(200, {"status": "signed_out"})
                return
            if path == "/api/v1/catalog" and not post:
                self.send_json(200, dict(strategies=[dict(id=FIXTURE_STRATEGY,
                     status="SYNTHETIC_CONTRACT_FIXTURE_ONLY", real_trading_eligible=False)]
                     + [dict(id=x, status="REJECTED", real_trading_eligible=False) for x in sorted(REJECTED)],
                     markets=[dict(instrument=x, status="UNVERIFIED", feed_connected=False)
                              for x in ("BTC", "ETH", "SOL", "US equities", "ETFs")],
                     live_enabled_in_any_jurisdiction=False))
                return
            parts = path.strip("/").split("/")
            if len(parts) not in {4, 5} or parts[:3] != ["api", "v1", "accounts"]:
                self.send_json(404, {"status": "not_found"})
                return
            account_id = parts[3]
            engine, store = self.server.engine, self.server.engine.store
            # Authorise before evaluating/returning any account-specific input.
            with store.transaction() as db:
                store.account(db, principal, account_id, write=post)
            if not post and len(parts) == 4:
                bundle = store.bundle(principal, account_id)
                snap, events, _ = bundle
                snap.update(journal=events[-200:], analytics=describe(snap, events),
                            reconciliation=reconcile(store, principal, account_id, bundle=bundle))
                self.send_json(200, snap)
                return
            if not post:
                self.send_json(404, {"status": "not_found"})
                return
            body, now = self._body(), timestamp()
            if len(parts) == 5 and parts[4] == "control" and set(body) == {"action"}:
                engine.control(principal, account_id, body["action"], now)
                result = dict(status="recorded")
            elif len(parts) == 5 and parts[4] == "fixture" and set(body) == {"action", "key"}:
                # Demo controls cannot select a provider, strategy, tenant or risk policy.
                if body["action"] not in {"cycle", "close", "gap"}:
                    raise ContractError("unsupported fixture action")
                quote = synthetic_quote(now, midpoint="95" if body["action"] == "gap" else "100")
                if body["action"] == "close":
                    result = engine.close_position(principal, account_id, quote, now, key=body["key"])
                else:
                    proposal = Proposal(account_id, "TEST/AUD", FIXTURE_STRATEGY, "LONG", "2", "98", body["key"])
                    result = engine.autonomous_cycle(principal, proposal, quote, now)
            elif len(parts) == 5 and parts[4] == "cycle" and set(body) == {"proposal", "quote"}:
                proposal = Proposal(**body["proposal"])
                if proposal.account_id != account_id:
                    raise Forbidden("account identity mismatch")
                result = engine.autonomous_cycle(principal, proposal, Quote(**body["quote"]), now)
            else:
                raise ContractError("unsupported request contract")
            self.send_json(200, result)
        except Forbidden:
            self.send_json(403 if self.headers.get("Authorization") else 401, {"status": "access_denied"})
        except (ValueError, TypeError, KeyError, UnicodeError, OverflowError):
            self.send_json(400, {"status": "invalid_request"})
        except (OSError, RuntimeError):
            self.send_json(503, {"status": "unavailable"})

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle(post=True)
