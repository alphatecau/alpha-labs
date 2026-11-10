"""Disposable PostgreSQL credential rotation acceptance. Never run on live DB."""
import os
import unittest
import psycopg
from disposable_pg_guard import require_disposable_ci_database


@unittest.skipUnless(os.getenv("ALPHA_TEST_PG_DSN"), "isolated PostgreSQL only")
class RotationAcceptance(unittest.TestCase):
    def test_role_password_rotation_and_revocation(self):
        dsn = os.environ["ALPHA_TEST_PG_DSN"]
        require_disposable_ci_database(dsn)
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute("CREATE ROLE alpha_rotation_ci LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD 'synthetic-old'")
            try:
                with psycopg.connect(dsn, user="alpha_rotation_ci", password="synthetic-old") as old:
                    self.assertEqual(old.execute("SELECT current_user").fetchone()[0], "alpha_rotation_ci")
                admin.execute("ALTER ROLE alpha_rotation_ci PASSWORD 'synthetic-new'")
                with self.assertRaises(psycopg.OperationalError):
                    psycopg.connect(dsn, user="alpha_rotation_ci", password="synthetic-old", connect_timeout=2)
                with psycopg.connect(dsn, user="alpha_rotation_ci", password="synthetic-new") as new:
                    self.assertEqual(new.execute("SELECT current_user").fetchone()[0], "alpha_rotation_ci")
                admin.execute("ALTER ROLE alpha_rotation_ci NOLOGIN")
                with self.assertRaises(psycopg.OperationalError):
                    psycopg.connect(dsn, user="alpha_rotation_ci", password="synthetic-new", connect_timeout=2)
            finally:
                admin.execute("DROP ROLE alpha_rotation_ci")


if __name__ == "__main__":
    unittest.main()
