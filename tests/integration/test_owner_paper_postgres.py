"""Actual durable identity/quota database plus SQLite paper ledger; fake quotes."""
import io
import json
import http.client
import os
import sqlite3
import tempfile
import threading
import re
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import Mock
from wsgiref.simple_server import make_server, WSGIRequestHandler

import psycopg

from alpha_lab.research.coinbase_paper_book import parse_book
from alpha_lab.research.live_paper_session import LivePaperSession
from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.paper_market_feed import PaperMarketFeed
from alpha_lab.research.postgres_paper_security import PostgresIdentityLimiter, PostgresPaperOwnership, SCHEMA
from deployment.account_role_research_reader import AccountRoleResearchReader
from deployment.owner_paper_bff import OwnerPaperBFF
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions, SCHEMA as SESSION_SCHEMA
from deployment.postgres_paper_checkpoints import PostgresPaperCheckpoints, checkpoint_schema
from deployment.staging_authenticated_bff import StagingResearchBFF
from deployment.verified_proxy_ingress import VerifiedProxyIngress
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
        self.admin.execute(checkpoint_schema(self.owner))
        self.admin.execute("CREATE ROLE alpha_owner_checkpoint LOGIN NOINHERIT PASSWORD 'synthetic-checkpoint-only'")
        self.admin.execute("GRANT SELECT,INSERT ON public.paper_journal_checkpoints TO alpha_owner_checkpoint")
        self.checkpoints = PostgresPaperCheckpoints(self.checkpoint_connect, owner_id=self.owner,
                                                   verification_key=bytes(range(32)))
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = datetime.now(timezone.utc)
        self.feed = PaperMarketFeed(fetch=self.fetch, clock=lambda: self.now)
        with ThreadPoolExecutor(3) as pool:
            self.feed.poll(pool)
        self.paper = LivePaperSession(self.directory.name, self.owner, self.feed, clock=lambda: self.now,
                                      checkpoint_store=self.checkpoints)
        self.addCleanup(self.paper.close)
        self.app = self.build()

    def connect(self):
        return psycopg.connect(self.dsn)

    def checkpoint_connect(self):
        return psycopg.connect(self.dsn, user="alpha_owner_checkpoint", password="synthetic-checkpoint-only")

    def drop_fixture(self):
        self.admin.execute("DROP TABLE IF EXISTS public.paper_journal_checkpoints")
        self.admin.execute("DROP ROLE IF EXISTS alpha_owner_checkpoint")
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

    def test_checkpoint_role_cannot_delete_modify_rebind_or_bypass_capability_checks(self):
        for sql in ("DELETE FROM public.paper_journal_checkpoints", "UPDATE public.paper_journal_checkpoints SET head=repeat('a',64)",
                    "TRUNCATE public.paper_journal_checkpoints", "ALTER TABLE public.paper_journal_checkpoints DROP CONSTRAINT checkpoint_owner_binding"):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege), self.checkpoint_connect() as conn:
                conn.execute(sql)
        for store in (PostgresPaperCheckpoints(self.connect, owner_id=self.owner, verification_key=bytes(range(32))),
                      PostgresPaperCheckpoints(self.checkpoint_connect, owner_id="oidc_" + "b" * 64, verification_key=bytes(range(32))),
                      PostgresPaperCheckpoints(self.checkpoint_connect, owner_id=self.owner, verification_key=b"x" * 32)):
            with self.assertRaises(PermissionError):
                store.load()
        self.admin.execute("GRANT UPDATE ON public.paper_journal_checkpoints TO alpha_owner_checkpoint")
        try:
            with self.assertRaises(PermissionError):
                self.checkpoints.ready()
        finally:
            self.admin.execute("REVOKE UPDATE ON public.paper_journal_checkpoints FROM alpha_owner_checkpoint")

    def test_protected_checkpoint_rejects_deleted_committed_fill_on_restart(self):
        self.arm()
        self.assertEqual(self.request("orders", self.order())[0], 200)
        self.paper.close()
        with sqlite3.connect(self.directory.name + "/alpha-paper.sqlite3") as conn:
            conn.execute("DELETE FROM events")
        with self.assertRaisesRegex(ValueError, "checkpoint mismatch"):
            LivePaperSession(self.directory.name, self.owner, self.feed, clock=lambda: self.now,
                             checkpoint_store=self.checkpoints)

    def test_checkpointed_restart_replays_once_without_rearming(self):
        self.arm()
        self.assertEqual(self.request("orders", self.order())[0], 200)
        self.paper.close()
        recovered = LivePaperSession(self.directory.name, self.owner, self.feed, clock=lambda: self.now,
                                      checkpoint_store=self.checkpoints)
        try:
            self.assertTrue(recovered.runtime.ledger.halted)
            self.assertEqual(recovered.runtime.ledger.sequence, 1)
            self.assertEqual(recovered.order(self.order())["status"], "ALREADY_COMMITTED")
            self.assertEqual(recovered.runtime.ledger.sequence, 1)
        finally:
            recovered.close()

    def test_concurrent_checkpoint_cas_has_one_winner_and_owner_is_immutable(self):
        barrier = threading.Barrier(2)

        def advance(head):
            barrier.wait(timeout=5)
            try:
                self.checkpoints.record(sequence=1, head=head, expected_sequence=0, expected_head="0" * 64)
                return "recorded"
            except PermissionError:
                return "rejected"

        with ThreadPoolExecutor(2) as pool:
            outcomes = list(pool.map(advance, ("a" * 64, "b" * 64)))
        self.assertCountEqual(outcomes, ["recorded", "rejected"])
        self.assertEqual(self.admin.execute("SELECT count(*) FROM paper_journal_checkpoints").fetchone()[0], 2)
        with self.assertRaises(psycopg.errors.CheckViolation), self.checkpoint_connect() as conn:
            conn.execute("INSERT INTO public.paper_journal_checkpoints VALUES(2,%s,%s,'synthetic')",
                         ("oidc_" + "b" * 64, "c" * 64))

    def test_checkpoint_outage_after_fill_commit_blocks_ack_and_unanchored_restart(self):
        self.arm()
        append = self.paper.runtime.journal.append

        def interrupt(*args, **kwargs):
            head = append(*args, **kwargs)
            self.admin.execute("ALTER TABLE paper_journal_checkpoints RENAME TO unavailable_checkpoints")
            return head

        self.paper.runtime.journal.append = interrupt
        try:
            code, result = self.request("orders", self.order())
            self.assertEqual(code, 503)
            self.assertEqual(result["error"], "CHECKPOINT_HALT")
            self.assertEqual(self.paper.runtime.ledger.sequence, 1)
            self.assertTrue(self.paper.runtime.ledger.halted)
        finally:
            self.admin.execute("ALTER TABLE unavailable_checkpoints RENAME TO paper_journal_checkpoints")
        self.paper.close()
        with self.assertRaisesRegex(ValueError, "checkpoint mismatch"):
            LivePaperSession(self.directory.name, self.owner, self.feed, clock=lambda: self.now,
                             checkpoint_store=self.checkpoints)

    def test_loopback_http_boundary_uses_real_sessions_csrf_quota_and_checkpointed_orders(self):
        class Quiet(WSGIRequestHandler):
            def log_message(self, *args):
                pass

        wrapped = VerifiedProxyIngress(self.app, "https://owner.example", trusted_peer_cidrs=["127.0.0.1/32"])
        server = make_server("127.0.0.1", 0, wrapped, handler_class=Quiet)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(path, payload=None, **extra):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            try:
                headers = {"Host": "owner.example", "X-Forwarded-Proto": "https",
                           "Cookie": "__Host-alpha_session=" + self.sid,
                           "Origin": "https://owner.example", "Content-Type": "application/json", **extra}
                conn.request("POST" if payload is not None else "GET", path,
                             json.dumps(payload) if payload is not None else None, headers)
                response = conn.getresponse()
                return response.status, response.read()
            finally:
                conn.close()

        try:
            code, html = request("/owner-paper/")
            self.assertEqual(code, 200)
            token = re.search(rb'name="alpha-csrf" content="([a-f0-9]{64})"', html).group(1).decode()
            self.assertNotIn(self.sid.encode(), html)
            self.assertEqual(request("/api/v1/paper/state", **{"X-Forwarded-For": "127.0.0.1"})[0], 403)
            self.assertEqual(request("/api/v1/paper/state", Cookie="")[0], 401)
            code, body = request("/api/v1/paper/state")
            self.assertEqual(code, 200)
            revision = json.loads(body)["risk"]["revision"]
            control = {"action": "arm", "revision": revision}
            self.assertEqual(request("/api/v1/paper/control", control)[0], 403)
            csrf = {"X-Alpha-CSRF": token}
            self.assertEqual(request("/api/v1/paper/control", control, **csrf)[0], 200)
            self.assertEqual(request("/api/v1/paper/orders", self.order(), Cookie="__Host-alpha_session=" + self.other, **csrf)[0], 403)
            self.assertEqual(request("/api/v1/paper/orders", self.order(), **csrf)[0], 200)
            self.assertEqual(json.loads(request("/api/v1/paper/orders", self.order(), **csrf)[1])["status"], "ALREADY_COMMITTED")
            self.sessions.revoke(self.sid)
            self.assertEqual(request("/api/v1/paper/state")[0], 403)
            self.assertTrue(self.paper.runtime.ledger.halted)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
