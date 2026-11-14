"""Two independent PostgreSQL LOGIN connections, disposable CI only.

This tests real database-enforced isolation; it does not claim Auth0/BFF acceptance.
"""
import os
import unittest
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

DB = "alpha_disposable_ci"
HOST = "127.0.0.1"
ROLES = ("alpha_ci_tenant_a", "alpha_ci_tenant_b")

def guarded_dsn():
    if os.getenv("ALPHA_DISPOSABLE_PG_CI") != "1":
        raise RuntimeError("CI disposable database marker required")
    dsn = os.environ["ALPHA_TEST_PG_DSN"]
    d = conninfo_to_dict(dsn)
    if d.get("host") != HOST or d.get("dbname") != DB or d.get("user") != "postgres" or str(d.get("port")) != "5432":
        raise RuntimeError("refusing unapproved database target")
    return dsn

class TwoLoginIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = psycopg.connect(guarded_dsn(), autocommit=True)
        for role in ROLES:
            cls.admin.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD 'ci-only'").format(sql.Identifier(role)))
        cls.admin.execute("CREATE TABLE public.alpha_ci_tenant_rows (owner_role name NOT NULL, value text NOT NULL)")
        cls.admin.execute("INSERT INTO public.alpha_ci_tenant_rows VALUES (%s,'a'),(%s,'b')", ROLES)
        cls.admin.execute("ALTER TABLE public.alpha_ci_tenant_rows ENABLE ROW LEVEL SECURITY")
        cls.admin.execute("ALTER TABLE public.alpha_ci_tenant_rows FORCE ROW LEVEL SECURITY")
        cls.admin.execute("CREATE POLICY tenant_only ON public.alpha_ci_tenant_rows FOR SELECT USING (owner_role = SESSION_USER)")
        cls.admin.execute("REVOKE ALL ON public.alpha_ci_tenant_rows FROM PUBLIC")
        for role in ROLES:
            cls.admin.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
            cls.admin.execute(sql.SQL("GRANT SELECT ON public.alpha_ci_tenant_rows TO {}").format(sql.Identifier(role)))

    @classmethod
    def tearDownClass(cls):
        try:
            cls.admin.execute("DROP TABLE IF EXISTS public.alpha_ci_tenant_rows")
            for role in ROLES:
                cls.admin.execute(sql.SQL("REVOKE USAGE ON SCHEMA public FROM {}").format(sql.Identifier(role)))
                cls.admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
        finally:
            cls.admin.close()

    def login(self, role):
        return psycopg.connect(host=HOST, port=5432, dbname=DB, user=role, password="ci-only", sslmode="disable")

    def test_each_login_sees_only_own_row_even_with_forged_guc(self):
        for role, other in ((ROLES[0], ROLES[1]), (ROLES[1], ROLES[0])):
            with self.subTest(role=role), self.login(role) as conn:
                conn.execute("SELECT set_config('alpha_labs.owner_id', %s, false)", (other,))
                self.assertEqual(conn.execute("SELECT owner_role FROM public.alpha_ci_tenant_rows").fetchall(), [(role,)])
                self.assertEqual(conn.execute("SELECT value FROM public.alpha_ci_tenant_rows WHERE owner_role=%s", (other,)).fetchall(), [])

    def test_role_switch_and_write_denied(self):
        for role, other in ((ROLES[0], ROLES[1]), (ROLES[1], ROLES[0])):
            with self.subTest(role=role):
                for statement in (sql.SQL("SET ROLE {}").format(sql.Identifier(other)), sql.SQL("SET SESSION AUTHORIZATION {}").format(sql.Identifier(other)), sql.SQL("DELETE FROM public.alpha_ci_tenant_rows")):
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        with self.login(role) as conn:
                            conn.execute(statement)

    def test_rls_forced_and_roles_unprivileged(self):
        with self.admin.cursor() as cur:
            cur.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='public.alpha_ci_tenant_rows'::regclass")
            self.assertEqual(cur.fetchone(), (True, True))
            cur.execute("SELECT rolname FROM pg_roles WHERE rolname=ANY(%s) AND (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb)", (list(ROLES),))
            self.assertEqual(cur.fetchall(), [])

if __name__ == "__main__":
    unittest.main()
