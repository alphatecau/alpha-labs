"""Adversarial tests of real restricted logins and both authenticated read routes."""
import json
import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg import sql

from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.postgres_paper_security import PostgresPaperOwnership, SCHEMA as OWNERSHIP_SCHEMA
from deployment.account_role_research_reader import AccountRoleResearchReader
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions, SCHEMA as SESSION_SCHEMA
from deployment.staging_authenticated_bff import StagingResearchBFF
from deployment.tenant_credential_broker import TenantCredentialBroker
from disposable_pg_guard import require_disposable_ci_database
from tenant_research_fixture import TenantResearchFixture


@unittest.skipUnless(os.getenv("ALPHA_TEST_PG_DSN"), "disposable PostgreSQL only")
class RoleIsolationTests(unittest.TestCase):
    def setUp(self):
        self.dsn = require_disposable_ci_database(os.environ["ALPHA_TEST_PG_DSN"])
        self.admin = psycopg.connect(self.dsn, autocommit=True)
        self.addCleanup(self.admin.close)
        self.issuer = "https://issuer.example/"
        self.a, self.b, self.unknown = [
            PostgresOpaqueSessions._owner(subject, self.issuer)
            for subject in ("alice", "bob", "unprovisioned")
        ]
        self.fixture = TenantResearchFixture(self.admin, self.dsn, (self.a, self.b))
        self.addCleanup(self.fixture.cleanup)
        self.fixture.install()
        self.reader = self.fixture.reader()

    def login(self, owner):
        return self.fixture.connect(**self.fixture.credentials[owner])

    def role(self, owner):
        return sql.Identifier(self.fixture.credentials[owner]["user"])

    def test_isolated_reader_and_unprovisioned_owner(self):
        self.assertEqual([r["run_id"] for r in self.reader.list_runs(self.a)], ["test-0"])
        self.assertEqual([r["run_id"] for r in self.reader.list_runs(self.b)], ["test-1"])
        with self.assertRaises(PermissionError):
            self.reader.list_runs(self.unknown)

    def test_guc_role_switch_and_session_authorization_fail_in_both_directions(self):
        for owner, other, expected in ((self.a, self.b, "test-0"), (self.b, self.a, "test-1")):
            with self.subTest(owner=expected):
                with self.login(owner) as conn:
                    conn.execute("SELECT set_config('alpha_labs.owner_id', %s, false)", (other,))
                    self.assertEqual(conn.execute("SELECT run_id FROM public.alpha_role_research").fetchall(),
                                     [(expected,)])
                    self.assertEqual(conn.execute(
                        "SELECT run_id FROM public.alpha_role_research WHERE owner_role = %s",
                        (self.fixture.credentials[other]["user"],)).fetchall(), [])
                for command in ("SET ROLE {}", "SET SESSION AUTHORIZATION {}"):
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege), self.login(owner) as conn:
                        conn.execute(sql.SQL(command).format(self.role(other)))

    def test_login_has_no_effective_write_privileges_in_read_write_transaction(self):
        for owner in (self.a, self.b):
            for query in ("UPDATE public.alpha_role_research SET run_id='forged'",
                          "DELETE FROM public.alpha_role_research",
                          "INSERT INTO public.alpha_role_research VALUES (session_user, 'forged', 'x')",
                          "TRUNCATE public.alpha_role_research"):
                with self.subTest(query=query), self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.login(owner) as conn:
                        conn.read_only = False
                        self.assertEqual(conn.execute("SHOW transaction_read_only").fetchone(), ("off",))
                        conn.execute(query)

    def test_pool_reuse_rejects_wrong_login_and_privileged_impersonation(self):
        with self.login(self.a) as reused:
            reused.autocommit = True
            reused.execute("SELECT set_config('alpha_labs.owner_id', %s, false)", (self.b,))

            @contextmanager
            def checked_out_connection(**kwargs):
                yield reused

            pooled = self.fixture.reader(checked_out_connection)
            self.assertEqual(pooled.list_runs(self.a)[0]["run_id"], "test-0")
            with self.assertRaisesRegex(PermissionError, "unsafe database identity"):
                pooled.list_runs(self.b)
            self.assertEqual(pooled.list_runs(self.a)[0]["run_id"], "test-0")

        with psycopg.connect(self.dsn, autocommit=True) as reused:
            reused.execute(sql.SQL("SET SESSION AUTHORIZATION {}").format(self.role(self.a)))
            self.assertEqual(reused.execute("SELECT session_user = current_user").fetchone(), (True,))
            with self.assertRaisesRegex(PermissionError, "unsafe database identity"):
                pooled.list_runs(self.a)

    def test_misbound_secret_does_not_open_a_connection(self):
        reader = AccountRoleResearchReader(TenantCredentialBroker(
            lambda owner: self.fixture.credentials[self.b],
            lambda **kwargs: self.fail("misbound credential opened a connection")))
        with self.assertRaisesRegex(PermissionError, "invalid tenant credential configuration"):
            reader.list_runs(self.a)

    def test_policy_and_effective_privilege_drift_fail_closed(self):
        a, b = self.role(self.a), self.role(self.b)
        for statement, reverse, parameters in (
            ("ALTER TABLE public.alpha_role_research NO FORCE ROW LEVEL SECURITY",
             "ALTER TABLE public.alpha_role_research FORCE ROW LEVEL SECURITY", ()),
            ("CREATE POLICY unsafe ON public.alpha_role_research USING (true)",
             "DROP POLICY unsafe ON public.alpha_role_research", ()),
            ("GRANT UPDATE (run_id) ON public.alpha_role_research TO {}",
             "REVOKE UPDATE (run_id) ON public.alpha_role_research FROM {}", (a,)),
            ("ALTER TABLE public.alpha_role_research OWNER TO {}",
             "ALTER TABLE public.alpha_role_research OWNER TO postgres; "
             "GRANT SELECT ON public.alpha_role_research TO {}", (a,)),
            ("GRANT {} TO {}", "REVOKE {} FROM {}", (b, a)),
            ("ALTER ROLE {} BYPASSRLS", "ALTER ROLE {} NOBYPASSRLS", (a,)),
        ):
            # Expose each temporary mutation to a separate connection, then restore it.
            with self.subTest(statement=statement):
                self.admin.execute(sql.SQL(statement).format(*parameters))
                try:
                    with self.assertRaises(PermissionError):
                        self.reader.list_runs(self.a)
                finally:
                    self.admin.execute(sql.SQL(reverse).format(*parameters))
                self.assertEqual(self.reader.list_runs(self.a)[0]["run_id"], "test-0")

    def test_staging_routes_use_only_session_owner_and_fail_closed(self):
        self.admin.execute(SESSION_SCHEMA)
        self.admin.execute(OWNERSHIP_SCHEMA)
        self.addCleanup(self.admin.execute,
                        "DROP TABLE public.alpha_oidc_sessions, public.paper_ownership, public.identity_rate_limit")
        now = datetime(2026, 11, 12, tzinfo=timezone.utc)
        sessions = PostgresOpaqueSessions(lambda: psycopg.connect(self.dsn), clock=lambda: now)
        ownership = PostgresPaperOwnership(\n            lambda: psycopg.connect(self.dsn),\n            verify_provisioning_authority=lambda principal: (\n                principal.issuer == self.issuer and principal.subject in ("alice", "bob", "unprovisioned")\n            ),\n        )
        tokens = []
        for subject in ("alice", "bob", "unprovisioned"):
            ownership.provision(VerifiedPrincipal(subject=subject, issuer=self.issuer), "primary")
            tokens.append(sessions.create(subject, self.issuer))
        app = StagingResearchBFF(object(), object(), sessions, self.reader,
                                 origin="https://staging.example",
                                 authorize_owner=lambda owner: ownership.require_owner_id(owner, "primary"))

        def request(token, route="runs", **extra):
            status = []
            env = {"PATH_INFO": f"/api/v1/research/{route}", "REQUEST_METHOD": "GET",
                   "HTTP_COOKIE": "__Host-alpha_session=" + token, **extra}
            body = b"".join(app(env, lambda code, headers: status.append(code)))
            return status[0], body

        status, body = request(tokens[0], QUERY_STRING="owner=" + self.b, HTTP_X_OWNER_ID=self.b)
        self.assertEqual(status, "200 OK")
        self.assertEqual([r["run_id"] for r in json.loads(body)["data"]], ["test-0"])
        status, body = request(tokens[1], "summary", HTTP_X_OWNER_ID=self.a)
        self.assertEqual(status, "200 OK")
        self.assertEqual([r["run_id"] for r in json.loads(body)["data"]["provenance"]["records"]], ["test-1"])
        self.assertEqual(request(tokens[2]), ("403 Forbidden", b""))
        self.assertEqual(request("x" * 48, HTTP_X_OWNER_ID=self.a), ("403 Forbidden", b""))

        self.admin.execute("ALTER TABLE public.alpha_role_research RENAME TO alpha_unavailable")
        try:
            self.assertEqual(request(tokens[0]), ("403 Forbidden", b""))
        finally:
            self.admin.execute("ALTER TABLE public.alpha_unavailable RENAME TO alpha_role_research")
        self.admin.execute(sql.SQL("ALTER ROLE {} NOLOGIN").format(self.role(self.a)))
        try:
            self.assertEqual(request(tokens[0]), ("503 Service Unavailable", b""))
        finally:
            self.admin.execute(sql.SQL("ALTER ROLE {} LOGIN").format(self.role(self.a)))

        sessions.revoke(tokens[0])
        self.assertEqual(request(tokens[0]), ("403 Forbidden", b""))
        now += timedelta(minutes=31)
        self.assertEqual(request(tokens[1], "summary"), ("403 Forbidden", b""))


if __name__ == "__main__":
    unittest.main()
