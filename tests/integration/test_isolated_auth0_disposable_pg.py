"""Disposable PostgreSQL 16 acceptance of Auth0 runtime role grants.

This test is skipped unless ALPHA_DISPOSABLE_PG_DSN points to a CI service
database. Never set it to an existing Render/production database.
"""
import os
import unittest
import uuid

from deployment.isolated_auth0_role_audit import audit_runtime_roles


@unittest.skipUnless(os.getenv("ALPHA_DISPOSABLE_PG_DSN"), "disposable CI PostgreSQL required")
class DisposableRoleAuditTests(unittest.TestCase):
    def test_restricted_runtime_roles(self):
        import psycopg

        dsn = os.environ["ALPHA_DISPOSABLE_PG_DSN"]
        prefix = "alpha_ci_" + uuid.uuid4().hex[:10]
        roles = {k: prefix + "_" + k for k in ("oauth", "session", "ownership")}
        tables = {
            "oauth": "alpha_oauth_transactions",
            "session": "alpha_oidc_sessions",
            "ownership": "paper_ownership",
        }

        def connect():
            return psycopg.connect(dsn)

        with connect() as conn:
            with conn.cursor() as cur:
                for role in roles.values():
                    cur.execute("CREATE ROLE " + role + " LOGIN")
                for table in tables.values():
                    cur.execute("CREATE TABLE IF NOT EXISTS public." + table +
                                " (id text PRIMARY KEY)")
                for purpose, role in roles.items():
                    grants = "SELECT" if purpose == "ownership" else "SELECT, INSERT, DELETE"
                    cur.execute("GRANT " + grants + " ON public." + tables[purpose] + " TO " + role)
        try:
            result = audit_runtime_roles(
                connect, oauth_role=roles["oauth"], session_role=roles["session"],
                ownership_role=roles["ownership"])
            self.assertEqual(set(result), {"oauth", "session", "ownership"})
            with connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("GRANT UPDATE ON public.alpha_oidc_sessions TO " + roles["session"])
            with self.assertRaises(PermissionError):
                audit_runtime_roles(
                    connect, oauth_role=roles["oauth"], session_role=roles["session"],
                    ownership_role=roles["ownership"])
        finally:
            with connect() as conn:
                with conn.cursor() as cur:
                    for purpose, role in roles.items():
                        cur.execute("REVOKE ALL ON public." + tables[purpose] + " FROM " + role)
                        cur.execute("DROP ROLE " + role)


if __name__ == "__main__":
    unittest.main()
