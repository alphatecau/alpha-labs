"""Exercise both research BFFs against one disposable PostgreSQL rate-limit store."""
import json
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import psycopg

from alpha_lab.research.oidc_durable_store import DurableOIDCStore
from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.postgres_paper_security import (
    PostgresIdentityLimiter, PostgresPaperOwnership, SCHEMA,
)
from deployment.account_role_research_reader import AccountRoleResearchReader
from deployment.bff_session_bridge import SessionOwnershipVerifier
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions, SCHEMA as SESSION_SCHEMA
from deployment.research_dashboard_bff import ResearchDashboardBFF
from deployment.research_readonly_api import ResearchReadOnlyAPI
from deployment.staging_authenticated_bff import StagingResearchBFF
from deployment.trusted_site_relay import TrustedSiteRelay
from disposable_pg_guard import require_disposable_ci_database


@unittest.skipUnless(os.getenv("ALPHA_TEST_PG_DSN"), "disposable PostgreSQL only")
class SharedBFFRateLimitTests(unittest.TestCase):
    def setUp(self):
        self.dsn = require_disposable_ci_database(os.environ["ALPHA_TEST_PG_DSN"])
        self.admin = psycopg.connect(self.dsn, autocommit=True)
        self.addCleanup(self.admin.close)
        self.admin.execute(SCHEMA)
        self.admin.execute(SESSION_SCHEMA)
        self.admin.execute("CREATE ROLE alpha_bff_quota LOGIN NOINHERIT PASSWORD 'synthetic-quota-only'")
        self.addCleanup(self.drop_fixture)
        self.admin.execute("GRANT SELECT, INSERT, UPDATE ON public.identity_rate_limit TO alpha_bff_quota")
        self.now = 600
        self.sessions = PostgresOpaqueSessions(self.connect)
        self.ownership = PostgresPaperOwnership(self.connect)
        self.alice = VerifiedPrincipal("alice", "https://issuer.example/")
        self.bob = VerifiedPrincipal("bob", self.alice.issuer)
        self.tokens, self.records = {}, {}
        for principal in (self.alice, self.bob):
            self.ownership.provision(principal, "primary")
            token = self.sessions.create(principal.subject, principal.issuer)
            self.tokens[principal] = token
            self.records[self.sessions.resolve_owner(token)] = {"run_id": f"private-{principal.subject}"}
        self.reader = Mock(spec=AccountRoleResearchReader)
        self.reader.list_runs.side_effect = lambda owner, **kwargs: [self.records[owner]]
        self.reader.summary.side_effect = lambda owner: {"recent": self.records[owner]}
        self.first, self.second = self.staging(), self.staging()

    def drop_fixture(self):
        self.admin.execute("DROP TABLE public.identity_rate_limit, public.paper_ownership, public.alpha_oidc_sessions")
        self.admin.execute("DROP ROLE alpha_bff_quota")

    def connect(self):
        return psycopg.connect(self.dsn)

    def quota_connect(self):
        return psycopg.connect(self.dsn, user="alpha_bff_quota", password="synthetic-quota-only")

    def limiter(self, limit=3, window=60):
        return PostgresIdentityLimiter(self.quota_connect, limit=limit, window=window, clock=lambda: self.now)

    def staging(self, limit=3, window=60):
        return StagingResearchBFF(
            object(), object(), PostgresOpaqueSessions(self.connect), self.reader,
            origin="https://staging.example", rate_limiter=self.limiter(limit, window),
            authorize_owner=lambda owner: self.ownership.require_owner_id(owner, "primary"))

    def legacy(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        sessions = DurableOIDCStore(directory.name + "/sessions.sqlite")
        self.addCleanup(sessions.close)
        verifier = SessionOwnershipVerifier(sessions=sessions, ownership=self.ownership, limiter=self.limiter())
        secret = "synthetic-relay-only-" + "x" * 48
        api = ResearchReadOnlyAPI(reader=self.reader, secret=secret)

        def backend(path, headers):
            status = []
            data = b"".join(api({"PATH_INFO": path, "REQUEST_METHOD": "GET",
                                 "HTTP_AUTHORIZATION": headers["Authorization"]},
                                lambda code, hdrs: status.append(code)))
            self.assertEqual(status, ["200 OK"])
            return json.loads(data)

        app = ResearchDashboardBFF(relay=TrustedSiteRelay(verifier, backend, secret))
        return app, sessions.create(self.alice.subject, self.alice.issuer)

    def request(self, app, token=None, route="/api/v1/research/runs", **overrides):
        env = {"PATH_INFO": route, "REQUEST_METHOD": "GET", "wsgi.url_scheme": "https", **overrides}
        if token:
            env["HTTP_COOKIE"] = "__Host-alpha_session=" + token
        response = []
        body = b"".join(app(env, lambda status, headers: response.append((status, dict(headers)))))
        status, headers = response[0]
        return int(status[:3]), headers, body

    def counters(self):
        return self.admin.execute("SELECT bucket, count FROM public.identity_rate_limit ORDER BY identity").fetchall()

    def test_both_bffs_share_quota_across_routes_sessions_and_instances(self):
        alice = self.tokens[self.alice]
        alice_second = self.sessions.create(self.alice.subject, self.alice.issuer)
        legacy, legacy_token = self.legacy()
        self.assertEqual(self.request(self.first, alice)[0], 200)
        self.assertEqual(self.request(self.second, alice_second, "/api/v1/research/summary")[0], 200)
        self.assertEqual(self.request(legacy, legacy_token, "/api/research/runs")[0], 200)
        for app, token, path in ((self.first, alice, "/api/v1/research/runs"),
                                 (self.second, alice_second, "/api/v1/research/summary"),
                                 (legacy, legacy_token, "/api/research/summary")):
            status, headers, body = self.request(app, token, path,
                                                 HTTP_X_OWNER_ID=self.sessions.resolve_owner(self.tokens[self.bob]))
            self.assertEqual(status, 429)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertNotIn(b"private-", body)
            self.assertNotIn(b"oidc_", body)
        self.assertEqual(self.counters(), [(600, 3)])
        self.assertEqual(self.request(self.second, self.tokens[self.bob])[0], 200)

    def test_concurrent_reads_cannot_exceed_quota(self):
        limit, workers = 7, 32
        apps = (self.staging(limit), self.staging(limit))
        paths = ("/api/v1/research/runs", "/api/v1/research/summary")
        barrier = threading.Barrier(workers)

        def request_at_once(index):
            barrier.wait(timeout=20)
            return self.request(apps[index % 2], self.tokens[self.alice], paths[index % 2])[0]

        with ThreadPoolExecutor(max_workers=workers) as pool:
            statuses = list(pool.map(request_at_once, range(workers)))
        self.assertEqual(sorted(statuses), [200] * limit + [429] * (workers - limit))
        self.assertEqual(self.counters(), [(600, limit)])
        self.assertEqual(self.reader.list_runs.call_count + self.reader.summary.call_count, limit)

    def test_unavailable_table_returns_503_without_reading_data_and_recovers(self):
        legacy, token = self.legacy()
        self.admin.execute("ALTER TABLE public.identity_rate_limit RENAME TO unavailable_rate_limit")
        try:
            for app, cookie, path in ((self.first, self.tokens[self.alice], "/api/v1/research/runs"),
                                      (self.second, self.tokens[self.alice], "/api/v1/research/summary"),
                                      (legacy, token, "/api/research/summary")):
                status, _, body = self.request(app, cookie, path)
                self.assertEqual(status, 503)
                self.assertNotIn(b"unavailable_rate_limit", body)
                self.assertNotIn(b"private-", body)
            self.reader.list_runs.assert_not_called()
            self.reader.summary.assert_not_called()
        finally:
            self.admin.execute("ALTER TABLE public.unavailable_rate_limit RENAME TO identity_rate_limit")
        self.assertEqual(self.request(self.first, self.tokens[self.alice])[0], 200)

    def test_authentication_ownership_and_read_only_guards_precede_quota(self):
        legacy, token = self.legacy()
        alice = self.tokens[self.alice]
        self.assertEqual(self.request(self.first)[0], 401)
        self.assertEqual(self.request(legacy, route="/api/research/runs")[0], 401)
        self.assertEqual(self.request(self.first, "x" * 48)[0], 403)
        self.assertEqual(self.request(self.first, alice, "/api/v1/orders", REQUEST_METHOD="POST")[0], 404)
        self.assertEqual(self.request(legacy, token, "/api/orders")[0], 404)
        self.assertEqual(self.request(self.first, alice, REQUEST_METHOD="POST")[0], 404)
        self.assertEqual(self.request(legacy, token, "/api/research/runs", REQUEST_METHOD="POST")[0], 405)
        self.ownership.revoke(self.alice, "primary")
        self.assertEqual(self.request(self.second, alice)[0], 403)
        self.assertEqual(self.request(legacy, token, "/api/research/runs")[0], 401)
        self.ownership.provision(self.alice, "primary")
        self.sessions.revoke(alice)
        self.assertEqual(self.request(self.first, alice, "/api/v1/research/summary")[0], 403)
        self.assertEqual(self.counters(), [])
        self.reader.list_runs.assert_not_called()
        self.reader.summary.assert_not_called()

    def test_late_statement_cannot_reopen_previous_window(self):
        for _ in range(3):
            self.assertEqual(self.request(self.first, self.tokens[self.alice])[0], 200)
        self.now = 660
        self.assertEqual(self.request(self.second, self.tokens[self.alice])[0], 200)
        self.now = 659
        self.assertEqual(self.request(self.first, self.tokens[self.alice])[0], 429)
        self.assertEqual(self.counters(), [(660, 1)])

    def test_coordinated_larger_window_recovers_at_new_boundary(self):
        self.now = 660
        self.assertEqual(self.request(self.first, self.tokens[self.alice])[0], 200)
        restarted = self.staging(window=120)
        self.assertEqual(self.request(restarted, self.tokens[self.alice])[0], 429)
        self.now = 720
        self.assertEqual(self.request(restarted, self.tokens[self.alice])[0], 200)
        self.assertEqual(self.counters(), [(720, 1)])

    def test_restricted_store_readiness_and_database_clock(self):
        limiter = PostgresIdentityLimiter(self.quota_connect, limit=2, window=120)
        self.assertTrue(limiter.ready())
        self.assertFalse(PostgresIdentityLimiter(self.connect).ready())
        with self.quota_connect() as connection:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                connection.execute("SELECT * FROM public.alpha_oidc_sessions")
        lower = self.admin.execute("SELECT floor(extract(epoch FROM statement_timestamp()) / 120) * 120").fetchone()[0]
        self.assertTrue(limiter.allow_owner(self.sessions.resolve_owner(self.tokens[self.alice])))
        upper = self.admin.execute("SELECT floor(extract(epoch FROM statement_timestamp()) / 120) * 120").fetchone()[0]
        bucket, count = self.counters()[0]
        self.assertTrue(lower <= bucket <= upper)
        self.assertEqual(count, 1)
        self.admin.execute("REVOKE UPDATE ON public.identity_rate_limit FROM alpha_bff_quota")
        self.assertFalse(limiter.ready())
        self.assertEqual(self.request(self.first, self.tokens[self.alice])[0], 503)


if __name__ == "__main__":
    unittest.main()
