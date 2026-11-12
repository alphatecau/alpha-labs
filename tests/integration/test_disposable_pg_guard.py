import os
import unittest
from unittest.mock import patch
from disposable_pg_guard import require_disposable_ci_database


class DisposableGuardTests(unittest.TestCase):
    def test_exact_local_disposable_target(self):
        with patch.dict(os.environ, {"ALPHA_DISPOSABLE_PG_CI": "1"}):
            self.assertEqual(
                require_disposable_ci_database(
                    "host=127.0.0.1 port=5432 dbname=alpha_rls_test user=postgres password=test"),
                "host=127.0.0.1 port=5432 dbname=alpha_rls_test user=postgres password=test")

    def test_marker_required(self):
        with patch.dict(os.environ, {"ALPHA_DISPOSABLE_PG_CI": "0"}):
            with self.assertRaises(RuntimeError):
                require_disposable_ci_database(
                    "host=127.0.0.1 port=5432 dbname=alpha_rls_test user=postgres")

    def test_legacy_security_fixture_requires_explicit_local_identity_and_marker(self):
        dsn = "host=localhost port=5432 dbname=alpha_security_test user=alpha_test"
        with patch.dict(os.environ, {"ALPHA_DISPOSABLE_PG_CI": "1"}):
            self.assertEqual(require_disposable_ci_database(
                dsn, database_name="alpha_security_test", user="alpha_test"), dsn)
            with self.assertRaises(RuntimeError):
                require_disposable_ci_database(dsn)
            with self.assertRaises(RuntimeError):
                require_disposable_ci_database(dsn, database_name="production", user="alpha_test")
        with patch.dict(os.environ, {"ALPHA_DISPOSABLE_PG_CI": "0"}):
            with self.assertRaises(RuntimeError):
                require_disposable_ci_database(dsn, database_name="alpha_security_test", user="alpha_test")

    def test_remote_and_non_disposable_targets_denied(self):
        targets = (
            "host=staging.example.com port=5432 dbname=alpha_rls_test user=postgres",
            "host=127.0.0.1 port=5432 dbname=alpha_labs user=postgres",
            "host=127.0.0.1 port=5432 dbname=alpha_rls_test user=reader",
            "host=127.0.0.1 hostaddr=10.1.2.3 port=5432 dbname=alpha_rls_test user=postgres",
            "host=127.0.0.1 port=5433 dbname=alpha_rls_test user=postgres",
            "dbname=alpha_rls_test user=postgres",
        )
        with patch.dict(os.environ, {"ALPHA_DISPOSABLE_PG_CI": "1"}):
            for dsn in targets:
                with self.subTest(dsn=dsn), self.assertRaises(RuntimeError):
                    require_disposable_ci_database(dsn)


if __name__ == "__main__":
    unittest.main()
