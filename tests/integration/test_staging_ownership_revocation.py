"""Real disposable PostgreSQL sessions + live ownership checks; no Auth0 access."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import psycopg
from disposable_pg_guard import require_disposable_ci_database
from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.postgres_paper_security import PostgresPaperOwnership
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions
from deployment.staging_authenticated_bff import StagingResearchBFF


@unittest.skipUnless(os.environ.get("ALPHA_TEST_PG_DSN"), "disposable PostgreSQL only")
class PostgreSQLOwnershipRevocationTests(unittest.TestCase):
    def setUp(self):
        self.dsn = require_disposable_ci_database(os.environ["ALPHA_TEST_PG_DSN"])
        self.admin = psycopg.connect(self.dsn, autocommit=True)
        self.addCleanup(self.admin.close)
        self.admin.execute("CREATE SCHEMA alpha_revocation_test")
        self.admin.execute("CREATE TABLE alpha_revocation_test.alpha_oidc_sessions (session_hash text PRIMARY KEY, owner_id text NOT NULL, expires_at timestamptz NOT NULL)")
        self.admin.execute("CREATE TABLE alpha_revocation_test.paper_ownership (owner_digest text NOT NULL, account text NOT NULL, active boolean NOT NULL, PRIMARY KEY(owner_digest,account))")
        for role in ("alpha_rev_sessions", "alpha_rev_ownership"):
            self.admin.execute(psycopg.sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD 'ci-only'").format(psycopg.sql.Identifier(role)))
            self.admin.execute(psycopg.sql.SQL("GRANT USAGE ON SCHEMA alpha_revocation_test TO {}").format(psycopg.sql.Identifier(role)))
        self.admin.execute("GRANT SELECT, INSERT, DELETE ON alpha_revocation_test.alpha_oidc_sessions TO alpha_rev_sessions")
        self.admin.execute("GRANT SELECT ON alpha_revocation_test.paper_ownership TO alpha_rev_ownership")
        self.admin.execute("ALTER ROLE alpha_rev_ownership SET default_transaction_read_only=on")
        self.addCleanup(self.cleanup_schema)
        self.now = datetime(2026, 11, 11, tzinfo=timezone.utc)
        self.sessions = PostgresOpaqueSessions(lambda: self.connection("alpha_rev_sessions"), clock=lambda: self.now)
        self.registry = PostgresPaperOwnership(lambda: self.connection("alpha_rev_ownership"))
        self.provisioner = PostgresPaperOwnership(lambda: self.connection("postgres"))
        self.alice = VerifiedPrincipal(subject="auth0|alice", issuer="https://issuer.example/")
        self.provisioner.provision(self.alice, "primary")
        self.token = self.sessions.create(self.alice.subject, self.alice.issuer)
        self.reader = SimpleNamespace(list_runs=Mock(return_value=[]), summary=Mock(return_value={}))
        self.app = self.application()

    def cleanup_schema(self):
        self.admin.execute("DROP SCHEMA alpha_revocation_test CASCADE")
        self.admin.execute("DROP ROLE alpha_rev_sessions, alpha_rev_ownership")

    def connection(self, user):
        return psycopg.connect(self.dsn, user=user, password="ci-only",
                               options="-c search_path=alpha_revocation_test,pg_catalog")

    def application(self):
        # Construct a separate registry instance to exercise cross-instance visibility.
        registry = PostgresPaperOwnership(lambda: self.connection("alpha_rev_ownership"))
        return StagingResearchBFF(object(), object(), self.sessions, self.reader,
                                 origin="https://staging.example",
                                 authorize_owner=lambda owner: registry.require_owner_id(owner, "primary"))

    def request(self, app=None, token=None, path="/api/v1/research/runs", **extra):
        status = []
        b"".join((app or self.app)({"PATH_INFO": path, "REQUEST_METHOD": "GET",
                                   "HTTP_COOKIE": "__Host-alpha_session=" + (token or self.token), **extra},
                                  lambda code, headers: status.append(code)))
        return status[0]

    def test_revocation_visible_to_existing_sessions_on_independent_instances(self):
        second = self.application()
        self.assertEqual(self.request(), "200 OK")
        self.assertEqual(self.request(second, path="/api/v1/research/summary"), "200 OK")
        self.provisioner.revoke(self.alice, "primary")
        self.reader.list_runs.reset_mock()
        self.reader.summary.reset_mock()
        self.assertEqual(self.request(), "403 Forbidden")
        self.assertEqual(self.request(second, path="/api/v1/research/summary"), "403 Forbidden")
        self.reader.list_runs.assert_not_called()
        self.reader.summary.assert_not_called()

    def test_expired_revoked_and_unprovisioned_sessions_are_denied(self):
        bob = self.sessions.create("auth0|bob", self.alice.issuer)
        other_issuer = self.sessions.create(self.alice.subject, "https://other.example/")
        owner = self.sessions.resolve_owner(self.token)
        for token in (bob, other_issuer):
            self.assertEqual(self.request(token=token, HTTP_X_OWNER_ID=owner,
                                          QUERY_STRING="owner=" + owner), "403 Forbidden")
        self.sessions.revoke(self.token)
        self.assertEqual(self.request(), "403 Forbidden")
        self.token = self.sessions.create(self.alice.subject, self.alice.issuer)
        self.now += timedelta(minutes=31)
        self.assertEqual(self.request(), "403 Forbidden")
        self.reader.list_runs.assert_not_called()

    def test_session_and_ownership_roles_cannot_cross_security_stores(self):
        with self.connection("alpha_rev_sessions") as conn:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SELECT * FROM paper_ownership")
        with self.connection("alpha_rev_ownership") as conn:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SELECT * FROM alpha_oidc_sessions")
        with self.connection("alpha_rev_ownership") as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute("UPDATE paper_ownership SET active=TRUE")


if __name__ == "__main__":
    unittest.main()
