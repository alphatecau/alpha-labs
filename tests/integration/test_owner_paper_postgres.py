"""Actual durable identity/quota database plus SQLite paper ledger; fake quotes."""
import io
import json
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import Mock

import psycopg

from alpha_lab.research.coinbase_paper_book import parse_book
from alpha_lab.research.live_paper_session import LivePaperSession
from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.paper_market_feed import PaperMarketFeed
from alpha_lab.research.postgres_paper_security import PostgresIdentityLimiter, PostgresPaperOwnership, SCHEMA
from deployment.account_role_research_reader import AccountRoleResearchReader
from deployment.owner_paper_bff import OwnerPaperBFF
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions, SCHEMA as SESSION_SCHEMA
from deployment.staging_authenticated_bff import StagingResearchBFF
from disposable_pg_guard import require_disposable_ci_database


@unittest.skipUnless(os.getenv("ALPHA_TEST_PG_DSN"), "explicit disposable PostgreSQL required")
class OwnerPaperPostgresTests(unittest.TestCase):
    def setUp(self):
        self.dsn = require_disposable_ci_database(os.environ["ALPHA_TEST_PG_DSN"])
        self.admin = psycopg.connect(self.dsn, autocommit=True)
        self.addCleanup(self.admin.close)
        self.admin.execute(SCHEMA)
        self.admin.execute(SESSION_SCHEMA)
        self.admin.execute("CREATE ROLE alpha_owner_quota LOGIN NOINHERIT PASSWORD 'synthetic-owner-quota'")
        self.addCleanup(self.drop_fixture)
        self.admin.execute("GRANT SELECT,INSERT,UPDATE ON public.identity_rate_limit TO alpha_owner_quota")
        self.sessions = PostgresOpaqueSessions(self.connect)
        self.ownership = PostgresPaperOwnership(self.connect)
        self.alice = VerifiedPrincipal("owner-alice", "https://issuer.example/")
        self.bob = VerifiedPrincipal("owner-bob", "https://issuer.example/")
        for principal in (self.alice, self.bob):
            self.ownership.provision(principal, "primary")
        self.sid = self.sessions.create(self.alice.subject, self.alice.issuer)
        self.other = self.sessions.create(self.bob.subject, self.bob.issuer)
        self.owner = self.sessions.resolve_owner(self.sid)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = datetime.now(timezone.utc)
        self.feed = PaperMarketFeed(fetch=self.fetch, clock=lambda: self.now)
        with ThreadPoolExecutor(3) as pool:
            self.feed.poll(pool)
        self.paper = LivePaperSession(self.directory.name, self.owner, self.feed, clock=lambda: self.now)
        self.addCleanup(self.paper.close)
        self.app = self.build()

    def connect(self):
        return psycopg.connect(self.dsn)

    def drop_fixture(self):
        self.admin.execute("DROP TABLE public.identity_rate_limit, public.paper_ownership, public.alpha_oidc_sessions")
        self.admin.execute("DROP ROLE alpha_owner_quota")

    def fetch(self, symbol):
        return parse_book(symbol, {"auction_mode": False, "sequence": 100,
            "time": self.now.isoformat().replace("+00:00", "Z"),
            "bids": [["100", "100", 1]], "asks": [["100.02", "100", 1]]}, self.now)

    def build(self, limit=7):
        limiter = PostgresIdentityLimiter(
            lambda: psycopg.connect(self.dsn, user="alpha_owner_quota", password="synthetic-owner-quota"),
            limit=limit, window=60, clock=lambda: 600)
        reader = Mock(spec=AccountRoleResearchReader)
        reader.list_runs.return_value = []
        research = StagingResearchBFF(object(), object(), self.sessions, reader,
            origin="https://owner.example", rate_limiter=limiter,
            authorize_owner=lambda owner: self.ownership.require_owner_id(owner, "primary"))
        return OwnerPaperBFF(research, self.paper, owner_id=self.owner, csrf_key=bytes(range(32)))

    def request(self, path="state", payload=None, *, sid=None, app=None):
        sid, app = sid or self.sid, app or self.app
        body = json.dumps(payload).encode() if payload is not None else b""
        env = {"PATH_INFO": path if path.startswith("/") else "/api/v1/paper/" + path,
            "REQUEST_METHOD": "POST" if payload is not None else "GET", "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body),
            "HTTP_COOKIE": "__Host-alpha_session=" + sid, "HTTP_ORIGIN": "https://owner.example",
            "HTTP_X_ALPHA_CSRF": app._csrf(sid), "HTTP_X_OWNER_ID": self.sessions._owner(self.bob.subject, self.bob.issuer)}
        response = []
        data = b"".join(app(env, lambda code, headers: response.append(int(code[:3]))))
        return response[0], json.loads(data) if data else {}

    def arm(self):
        code, state = self.request()
        self.assertEqual(code, 200)
        self.assertEqual(self.request("control", {"action": "arm", "revision": state["risk"]["revision"]})[0], 200)

    @staticmethod
    def order():
        return {"order_id": "postgres_owner_order_0001", "symbol": "SOL-USD", "side": "BUY",
                "quantity": "1", "stop_price": "90"}

    def test_two_instances_concurrent_duplicate_orders_share_account_quota(self):
        self.arm()
        second = self.build()
        self.admin.execute("DELETE FROM identity_rate_limit")
        barrier = threading.Barrier(16)

        def attempt(i):
            barrier.wait(timeout=10)
            return self.request("orders", self.order(), app=(self.app, second)[i % 2])

        with ThreadPoolExecutor(16) as pool:
            results = list(pool.map(attempt, range(16)))
        self.assertEqual(sum(code == 200 for code, _ in results), 7)
        self.assertEqual(sum(code == 429 for code, _ in results), 9)
        self.assertEqual(sum(data.get("status") == "SIMULATED_FILL" for _, data in results), 1)
        self.assertEqual(self.paper.runtime.ledger.sequence, 1)
        self.assertEqual(self.request("/api/v1/research/runs")[0], 429)
        self.assertEqual(self.request("control", {"action": "halt"})[0], 200)
        self.assertEqual(self.admin.execute("SELECT count FROM identity_rate_limit").fetchall(), [(7,)])

    def test_other_owner_revocation_expiry_and_current_ownership(self):
        self.assertEqual(self.request(sid=self.other)[0], 403)
        self.assertEqual(self.admin.execute("SELECT count(*) FROM identity_rate_limit").fetchone()[0], 0)
        self.arm()
        self.sessions.revoke(self.sid)
        self.app.on_market_update()
        self.assertTrue(self.paper.runtime.ledger.halted)
        self.assertEqual(self.request()[0], 403)
        self.sid = self.sessions.create(self.alice.subject, self.alice.issuer)
        self.admin.execute("UPDATE alpha_oidc_sessions SET expires_at=TIMESTAMPTZ '2000-01-01 UTC' WHERE session_hash=%s", (self.sessions._hash(self.sid),))
        self.assertEqual(self.request()[0], 403)
        self.sid = self.sessions.create(self.alice.subject, self.alice.issuer)
        self.ownership.revoke(self.alice, "primary")
        self.assertEqual(self.request("orders", self.order())[0], 403)
        self.assertEqual(self.paper.runtime.ledger.sequence, 0)

    def test_database_table_outage_halts_and_cannot_fall_back(self):
        self.arm()
        self.admin.execute("ALTER TABLE identity_rate_limit RENAME TO unavailable_identity_rate_limit")
        try:
            code, data = self.request("orders", self.order())
            self.assertEqual(code, 503)
            self.assertNotIn("fill", data)
            self.assertTrue(self.paper.runtime.ledger.halted)
            self.assertTrue(self.paper.fault)
            self.assertEqual(self.paper.runtime.ledger.sequence, 0)
        finally:
            self.admin.execute("ALTER TABLE unavailable_identity_rate_limit RENAME TO identity_rate_limit")
