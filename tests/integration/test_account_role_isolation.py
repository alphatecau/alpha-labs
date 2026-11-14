"""Disposable PostgreSQL tenant-role adversarial acceptance."""
import os
import unittest
from contextlib import contextmanager
import psycopg
from disposable_pg_guard import require_disposable_ci_database
from deployment.account_role_research_reader import AccountRoleResearchReader


@unittest.skipUnless(os.getenv("ALPHA_TEST_PG_DSN"), "disposable PostgreSQL only")
class RoleIsolationTests(unittest.TestCase):
    def setUp(self):
        dsn = os.environ["ALPHA_TEST_PG_DSN"]
        require_disposable_ci_database(dsn)
        self.dsn = dsn
        self.admin = psycopg.connect(dsn, autocommit=True)
        for role in ("alpha_tenant_a", "alpha_tenant_b"):
            self.admin.execute(
                "CREATE ROLE " + role + " LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD 'ci-only'"
            )
        self.admin.execute("CREATE TABLE public.alpha_role_research (owner_role name NOT NULL, run_id text NOT NULL, evidence_sha256 text NOT NULL, created_at timestamptz NOT NULL DEFAULT now())")
        self.admin.execute("INSERT INTO public.alpha_role_research(owner_role,run_id,evidence_sha256) VALUES ('alpha_tenant_a','a1',repeat('a',64)),('alpha_tenant_b','b1',repeat('b',64))")
        self.admin.execute("ALTER TABLE public.alpha_role_research ENABLE ROW LEVEL SECURITY")
        self.admin.execute("ALTER TABLE public.alpha_role_research FORCE ROW LEVEL SECURITY")
        self.admin.execute("CREATE POLICY alpha_tenant_policy ON public.alpha_role_research FOR SELECT TO alpha_tenant_a,alpha_tenant_b USING (owner_role=current_user)")
        self.admin.execute("REVOKE ALL ON public.alpha_role_research FROM PUBLIC")
        self.admin.execute("GRANT USAGE ON SCHEMA public TO alpha_tenant_a,alpha_tenant_b")
        self.admin.execute("GRANT SELECT ON public.alpha_role_research TO alpha_tenant_a,alpha_tenant_b")

        @contextmanager
        def resolver(owner):
            roles = {"verified_a": "alpha_tenant_a", "verified_b": "alpha_tenant_b"}
            if owner not in roles:
                raise PermissionError("unprovisioned owner")
            with psycopg.connect(self.dsn, user=roles[owner], password="ci-only") as conn:
                yield conn

        self.reader = AccountRoleResearchReader(resolver)
        self.resolver = resolver

    def tearDown(self):
        self.admin.execute("DROP TABLE IF EXISTS public.alpha_role_research")
        self.admin.execute("REVOKE USAGE ON SCHEMA public FROM alpha_tenant_a,alpha_tenant_b")
        self.admin.execute("DROP ROLE IF EXISTS alpha_tenant_a,alpha_tenant_b")
        self.admin.close()

    def test_isolated_reader_and_unprovisioned_owner(self):
        self.assertEqual([r["run_id"] for r in self.reader.list_runs("verified_a")], ["a1"])
        self.assertEqual([r["run_id"] for r in self.reader.list_runs("verified_b")], ["b1"])
        with self.assertRaises(PermissionError):
            self.reader.list_runs("unprovisioned")

    def test_arbitrary_sql_cannot_switch_tenant(self):
        with self.resolver("verified_a") as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('alpha_labs.owner_id','alpha_tenant_b',false)")
                cur.execute("SELECT run_id FROM public.alpha_role_research")
                self.assertEqual(cur.fetchall(), [("a1",)])
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute("SET ROLE alpha_tenant_b")
        with self.resolver("verified_b") as conn:
            self.assertEqual(conn.execute("SELECT run_id FROM public.alpha_role_research").fetchall(), [("b1",)])

    def test_write_denied(self):
        with self.resolver("verified_a") as conn:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                conn.execute("DELETE FROM public.alpha_role_research")


if __name__ == "__main__":
    unittest.main()
