"""Offline adversarial tests. Real PostgreSQL variants live in integration/."""
import io
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import Mock

from alpha_lab.research.coinbase_paper_book import PRODUCTS, parse_book
from alpha_lab.research.live_paper_api import create_app
from alpha_lab.research.live_paper_session import LivePaperSession
from alpha_lab.research.paper_market_feed import PaperMarketFeed
from alpha_lab.research.paper_checkpoint import seal_checkpoint
from alpha_lab.research.postgres_paper_security import PostgresIdentityLimiter, RateLimitExceeded
from deployment.account_role_research_reader import AccountRoleResearchReader
from deployment.owner_paper_bff import OwnerPaperBFF, create_owner_paper_application
from deployment.postgres_paper_checkpoints import PostgresPaperCheckpoints
from deployment.staging_authenticated_bff import StagingResearchBFF

OWNER = "oidc_" + "a" * 64
OTHER = "oidc_" + "b" * 64
ORIGIN = "https://paper.example"
SID = "synthetic-session-owner"
KEY = bytes(range(32))


class OwnerPaperBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = datetime(2026, 11, 12, tzinfo=timezone.utc)
        self.feed = PaperMarketFeed(clock=lambda: self.now, fetch=self.fetch_book)
        with ThreadPoolExecutor(3) as pool:
            self.feed.poll(pool)
        # Unit-only checkpoint double; integration tests use the actual restricted PG role.
        self.checkpoints = Mock(spec=PostgresPaperCheckpoints)
        self.checkpoints.owner_id = OWNER
        self.checkpoints.verification_key = KEY
        self.checkpoints.envelope = None
        self.checkpoints.load.side_effect = lambda: self.checkpoints.envelope
        self.checkpoints.ready.return_value = True

        def record(**values):
            self.checkpoints.envelope = seal_checkpoint(sequence=values["sequence"], head=values["head"], secret=KEY)
            return self.checkpoints.envelope

        self.checkpoints.record.side_effect = record
        self.paper = LivePaperSession(self.directory.name, OWNER, self.feed, clock=lambda: self.now,
                                      checkpoint_store=self.checkpoints)
        self.addCleanup(self.paper.close)
        self.sessions = Mock()
        self.sessions.resolve_owner.side_effect = lambda sid: {SID: OWNER, "other-session": OTHER}[sid]
        self.limiter = Mock(spec=PostgresIdentityLimiter)
        self.limiter.allow_owner.return_value = True
        self.limiter.ready.return_value = True
        self.research = StagingResearchBFF(
            object(), object(), self.sessions, Mock(spec=AccountRoleResearchReader), origin=ORIGIN,
            authorize_owner=Mock(return_value=True), rate_limiter=self.limiter)
        self.app = OwnerPaperBFF(self.research, self.paper, owner_id=OWNER, csrf_key=KEY)

    def fetch_book(self, symbol):
        return parse_book(symbol, {"auction_mode": False, "sequence": 100,
            "time": self.now.isoformat().replace("+00:00", "Z"),
            "bids": [["100", "100", 1]], "asks": [["100.02", "100", 1]]}, self.now)

    def request(self, path="state", payload=None, *, sid=SID, app=None, raw=None, **headers):
        body = json.dumps(payload).encode() if raw is None else raw
        env = {"PATH_INFO": path if path.startswith("/") else "/api/v1/paper/" + path,
               "REQUEST_METHOD": "GET" if payload is None and raw is None else "POST",
               "CONTENT_LENGTH": str(len(body)) if payload is not None or raw is not None else "0",
               "CONTENT_TYPE": "application/json", "wsgi.input": io.BytesIO(body),
               "HTTP_COOKIE": "__Host-alpha_session=" + sid if sid else "",
               "HTTP_ORIGIN": ORIGIN, "HTTP_X_ALPHA_CSRF": self.app._csrf(sid or ""),
               "HTTP_HOST": "paper.example", "HTTP_X_FORWARDED_PROTO": "https",
               "REMOTE_ADDR": "127.0.0.1", **headers}
        response = []
        result = b"".join((app or self.app)(env, lambda status, h: response.append((int(status[:3]), dict(h)))))
        return response[0][0], response[0][1], result

    def arm(self):
        state = json.loads(self.request()[2])
        return self.request("control", {"action": "arm", "revision": state["risk"]["revision"]})

    @staticmethod
    def order():
        return {"order_id": "owner_paper_test_order_0001", "symbol": "SOL-USD", "side": "BUY",
                "quantity": "1", "stop_price": "90"}

    def test_owner_binding_forged_assertions_and_private_assets(self):
        for sid, expected in ((None, 401), ("other-session", 403)):
            for route in ("state", "/owner-paper/", "/owner-paper/paper.js"):
                self.assertEqual(self.request(route, sid=sid, HTTP_X_OWNER_ID=OWNER)[0], expected)
        self.limiter.allow_owner.assert_not_called()
        code, headers, page = self.request("/owner-paper/")
        self.assertEqual(code, 200)
        self.assertIn(self.app._csrf(SID).encode(), page)
        self.assertNotIn(SID.encode(), page)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        with self.assertRaises(ValueError):
            OwnerPaperBFF(self.research, self.paper, owner_id=OTHER, csrf_key=KEY)
        with self.assertRaises(RuntimeError):
            create_app()

    def test_post_requires_same_origin_session_bound_csrf_and_bounded_json(self):
        for headers in ({"HTTP_ORIGIN": "https://attacker.example"}, {"HTTP_X_ALPHA_CSRF": ""},
                        {"HTTP_X_ALPHA_CSRF": self.app._csrf("other-session")}):
            self.assertEqual(self.request("control", {"action": "halt"}, **headers)[0], 403)
        for raw in (b'{"action":"halt","action":"arm"}', b'[]', b'{' + b' ' * 2050):
            self.assertEqual(self.request("control", raw=raw)[0], 400)
        self.assertEqual(self.paper.runtime.ledger.sequence, 0)

    def test_arm_replay_duplicate_threads_conflicting_terms_and_halt(self):
        self.assertEqual(self.arm()[0], 200)
        with ThreadPoolExecutor(16) as pool:
            results = list(pool.map(lambda _: self.request("orders", self.order()), range(32)))
        self.assertTrue(all(code == 200 for code, _, _ in results))
        self.assertEqual(sum(json.loads(body)["status"] == "SIMULATED_FILL" for _, _, body in results), 1)
        self.assertEqual(self.paper.runtime.ledger.sequence, 1)
        self.assertEqual(self.request("orders", self.order() | {"quantity": "2"})[0], 409)
        self.assertEqual(self.request("control", {"action": "arm", "revision": 0})[0], 409)
        self.limiter.allow_owner.side_effect = RateLimitExceeded("quota")
        self.assertEqual(self.request()[0], 429)
        self.assertEqual(self.request("orders", self.order())[0], 429)
        self.assertEqual(self.request("control", {"action": "halt"})[0], 200)
        self.assertTrue(self.paper.runtime.ledger.halted)
        for path in ("/api/paper/orders", "/api/v1/paper/orders/", "/owner-paper/../index.html"):
            self.assertEqual(self.request(path, self.order())[0], 404)

    def test_revocation_expiry_ownership_and_database_outages_halt(self):
        self.assertEqual(self.arm()[0], 200)
        self.sessions.resolve_owner.side_effect = PermissionError("expired or revoked")
        self.app.on_market_update()
        self.assertTrue(self.paper.runtime.ledger.halted)
        self.assertEqual(self.request()[0], 403)
        self.sessions.resolve_owner.side_effect = OSError("database unavailable")
        self.assertEqual(self.request()[0], 503)
        self.assertTrue(self.paper.fault)

    def test_ownership_revoked_or_quota_unavailable_prevents_fills(self):
        self.assertEqual(self.arm()[0], 200)
        self.research.authorize_owner.return_value = False
        self.assertEqual(self.request("orders", self.order())[0], 403)
        self.assertTrue(self.paper.runtime.ledger.halted)
        self.assertEqual(self.paper.runtime.ledger.sequence, 0)

    def test_quota_dependency_outage_halts_and_never_returns_state(self):
        self.assertEqual(self.arm()[0], 200)
        self.limiter.allow_owner.side_effect = OSError("unavailable")
        code, _, body = self.request()
        self.assertEqual(code, 503)
        self.assertNotIn(b"portfolio", body)
        self.assertTrue(self.paper.fault)
        self.assertTrue(self.paper.runtime.ledger.halted)

    def test_sqlite_lock_contention_fails_closed_without_a_partial_fill(self):
        self.assertEqual(self.arm()[0], 200)
        self.paper.db.execute("PRAGMA busy_timeout=10")
        blocker = sqlite3.connect(self.directory.name + "/alpha-paper.sqlite3")
        try:
            blocker.execute("BEGIN IMMEDIATE")
            self.assertEqual(self.request("orders", self.order())[0], 503)
            self.assertTrue(self.paper.runtime.ledger.halted)
            self.assertEqual(self.paper.runtime.ledger.sequence, 0)
            self.assertEqual(self.paper.db.execute("SELECT count(*) FROM events").fetchone()[0], 0)
        finally:
            blocker.rollback()
            blocker.close()

    def test_factory_rejects_spoofed_proxy_and_never_starts_on_bad_config(self):
        self.feed.start = Mock()
        with self.assertRaises(ValueError):
            create_owner_paper_application(research=self.research, paper=self.paper, owner_id=OWNER,
                                          csrf_key=KEY, trusted_peer_cidrs=["0.0.0.0/0"])
        self.feed.start.assert_not_called()
        wrapped = create_owner_paper_application(research=self.research, paper=self.paper, owner_id=OWNER,
                                                 csrf_key=KEY, trusted_peer_cidrs=["127.0.0.1/32"])
        self.assertEqual(self.request(app=wrapped, REMOTE_ADDR="192.0.2.5")[0], 403)
        self.assertEqual(self.request(app=wrapped, HTTP_X_FORWARDED_FOR="127.0.0.1")[0], 403)
        self.assertEqual(self.request(app=wrapped)[0], 200)

    def test_owner_api_refuses_unprotected_offline_session(self):
        with tempfile.TemporaryDirectory() as directory:
            offline = LivePaperSession(directory, OWNER, self.feed, clock=lambda: self.now)
            try:
                with self.assertRaisesRegex(ValueError, "protected checkpoint"):
                    OwnerPaperBFF(self.research, offline, owner_id=OWNER, csrf_key=KEY)
            finally:
                offline.close()

    def test_checkpoint_failure_after_local_commit_never_acknowledges_or_refills(self):
        self.assertEqual(self.arm()[0], 200)
        self.checkpoints.record.side_effect = OSError("synthetic authority outage")
        self.assertEqual(self.request("orders", self.order())[0], 503)
        self.assertEqual(self.paper.runtime.ledger.sequence, 1)
        self.assertEqual(self.request("control", {"action": "halt"})[0], 200)
        self.assertTrue(self.paper.runtime.ledger.halted)
        self.assertEqual(self.request("orders", self.order())[0], 503)
        self.assertEqual(self.paper.runtime.ledger.sequence, 1)
