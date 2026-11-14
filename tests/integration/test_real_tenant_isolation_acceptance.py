"""Real PostgreSQL tenant-isolation adversarial acceptance.

Uses disposable CI PostgreSQL and real LOGIN roles, FORCE RLS, and the
production tenant reader. Never targets hosted or persistent databases.
"""
import os
import unittest

import psycopg
from psycopg import sql

from deployment.postgres_opaque_sessions import PostgresOpaqueSessions
from deployment.tenant_credential_broker import tenant_login_role
from disposable_pg_guard import require_disposable_ci_database
from tenant_research_fixture import TenantResearchFixture


@unittest.skipUnless(os.getenv("ALPHA_TEST_PG_DSN"), "disposable CI PostgreSQL required")
class RealTenantIsolationAcceptance(unittest.TestCase):
    def setUp(self):
        self.dsn = require_disposable_ci_database(os.environ["ALPHA_TEST_PG_DSN"])
        self.admin = psycopg.connect(self.dsn, autocommit=True)
        self.addCleanup(self.admin.close)
        issuer = "https://auth.example/"
        self.alice = PostgresOpaqueSessions._owner("auth0|alice", issuer)
        self.bob = PostgresOpaqueSessions._owner("auth0|bob", issuer)
        self.fixture = TenantResearchFixture(self.admin, self.dsn, (self.alice, self.bob))
        self.addCleanup(self.fixture.cleanup)
        self.fixture.install()
        self.reader = self.fixture.reader()

    def test_real_role_rls_filters_other_tenant_and_summary(self):
        for owner, other, expected in ((self.alice, self.bob, "test-0"),
                                       (self.bob, self.alice, "test-1")):
            with self.subTest(owner=owner):
                creds = self.fixture.credentials[owner]
                with self.fixture.connect(**creds) as conn:
                    own = conn.execute(
                        "SELECT run_id FROM public.alpha_role_research ORDER BY run_id").fetchall()
                    self.assertEqual(own, [(expected,)])
                    self.assertEqual(conn.execute(
                        "SELECT run_id FROM public.alpha_role_research WHERE owner_role=%s",
                        (tenant_login_role(other),)).fetchall(), [])
                    # Caller-controlled GUC cannot change the SESSION_USER RLS identity.
                    conn.execute("SELECT set_config('alpha_labs.owner_id', %s, false)", (other,))
                    self.assertEqual(conn.execute(
                        "SELECT run_id FROM public.alpha_role_research").fetchall(), [(expected,)])
                self.assertEqual([x["run_id"] for x in self.reader.list_runs(owner)], [expected])
                summary = self.reader.summary(owner)
                self.assertEqual([x["run_id"] for x in summary["provenance"]["records"]], [expected])

    def test_restricted_role_cannot_switch_or_write_other_tenant(self):
        for owner, other in ((self.alice, self.bob), (self.bob, self.alice)):
            creds = self.fixture.credentials[owner]
            other_role = sql.Identifier(tenant_login_role(other))
            for command in (
                sql.SQL("SET ROLE {}").format(other_role),
                sql.SQL("SET SESSION AUTHORIZATION {}").format(other_role),
                sql.SQL("UPDATE public.alpha_role_research SET run_id='forged'"),
                sql.SQL("DELETE FROM public.alpha_role_research"),
                sql.SQL("INSERT INTO public.alpha_role_research VALUES "
                        "(SESSION_USER, 'forged', 'forged')"),
            ):
                with self.subTest(owner=owner, command=str(command)):
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        with self.fixture.connect(**creds) as conn:
                            conn.execute(command)

    def test_reader_fails_closed_after_policy_or_grant_drift(self):
        role = sql.Identifier(tenant_login_role(self.alice))
        for mutate, restore in (
            ("ALTER TABLE public.alpha_role_research DISABLE ROW LEVEL SECURITY",
             "ALTER TABLE public.alpha_role_research ENABLE ROW LEVEL SECURITY"),
            ("ALTER TABLE public.alpha_role_research NO FORCE ROW LEVEL SECURITY",
             "ALTER TABLE public.alpha_role_research FORCE ROW LEVEL SECURITY"),
            ("GRANT UPDATE ON public.alpha_role_research TO {}",
             "REVOKE UPDATE ON public.alpha_role_research FROM {}"),
        ):
            with self.subTest(mutate=mutate):
                self.admin.execute(sql.SQL(mutate).format(role))
                try:
                    with self.assertRaises(PermissionError):
                        self.reader.list_runs(self.alice)
                finally:
                    self.admin.execute(sql.SQL(restore).format(role))
                self.assertEqual(self.reader.list_runs(self.alice)[0]["run_id"], "test-0")


if __name__ == "__main__":
    unittest.main()
