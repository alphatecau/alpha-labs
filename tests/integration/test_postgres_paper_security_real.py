"""Real PostgreSQL integration and concurrency checks (isolated CI only)."""

import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

try:
    import psycopg
except ImportError:
    psycopg = None

from alpha_lab.research.paper_account_service import VerifiedPrincipal
from disposable_pg_guard import require_disposable_ci_database
from alpha_lab.research.postgres_security_migration import (
    apply_schema,
    verify_schema,
    MIGRATION_ID,
)
from alpha_lab.research.postgres_paper_security import (
    PostgresPaperOwnership,
    PostgresIdentityLimiter,
    SCHEMA,
)


@unittest.skipUnless(
    psycopg is not None and os.getenv("ALPHA_TEST_POSTGRES_DSN"),
    "Requires explicit isolated PostgreSQL CI service",
)
class RealPostgresSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["ALPHA_TEST_POSTGRES_DSN"]
        require_disposable_ci_database(cls.dsn, database_name="alpha_security_test", user="alpha_test")
        cls.connect = staticmethod(lambda: psycopg.connect(cls.dsn))
        with cls.connect() as conn:
            conn.execute(SCHEMA)

    def setUp(self):
        with self.connect() as conn:
            conn.execute("TRUNCATE TABLE paper_ownership, identity_rate_limit")
        self.owner = VerifiedPrincipal(
            subject="integration_owner", issuer="https://test-issuer.example/"
        )

    def test_persisted_ownership_isolation_and_revocation(self):
        first = PostgresPaperOwnership(self.connect)
        second = PostgresPaperOwnership(self.connect)
        with self.assertRaises(PermissionError):
            second.require(self.owner, "primary")
        first.provision(self.owner, "primary")
        self.assertTrue(second.require(self.owner, "primary"))
        other = VerifiedPrincipal(subject="integration_other", issuer=self.owner.issuer)
        with self.assertRaises(PermissionError):
            second.require(other, "primary")
        first.revoke(self.owner, "primary")
        with self.assertRaises(PermissionError):
            second.require(self.owner, "primary")

    def test_atomic_rate_limit_under_concurrent_connections(self):
        limit = 12
        limiter = PostgresIdentityLimiter(
            self.connect, limit=limit, window=60, clock=lambda: 120
        )
        workers = 32
        barrier = threading.Barrier(workers)

        def attempt(_):
            barrier.wait(timeout=20)
            try:
                return limiter.allow(self.owner.issuer, self.owner.subject)
            except PermissionError:
                return False

        with ThreadPoolExecutor(max_workers=workers) as pool:
            outcomes = list(pool.map(attempt, range(workers)))
        self.assertEqual(sum(outcomes), limit)
        with self.connect() as conn:
            count = conn.execute("SELECT count FROM identity_rate_limit").fetchone()[0]
        self.assertEqual(count, limit)

    def test_explicit_migration_is_idempotent_and_verifiable(self):
        apply_schema(self.connect)
        apply_schema(self.connect)
        self.assertTrue(verify_schema(self.connect))
        with self.connect() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM alpha_schema_migrations WHERE id=%s",
                (MIGRATION_ID,),
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_same_subject_different_issuer_cannot_access_owner(self):
        registry = PostgresPaperOwnership(self.connect)
        registry.provision(self.owner, "primary")
        forged_issuer = VerifiedPrincipal(
            subject=self.owner.subject, issuer="https://other-issuer.example/"
        )
        with self.assertRaises(PermissionError):
            registry.require(forged_issuer, "primary")

    def test_shared_limit_across_independent_limiter_instances(self):
        def now():
            return 120
        first = PostgresIdentityLimiter(self.connect, limit=3, window=60, clock=now)
        second = PostgresIdentityLimiter(self.connect, limit=3, window=60, clock=now)
        self.assertTrue(first.allow(self.owner.issuer, self.owner.subject))
        self.assertTrue(second.allow(self.owner.issuer, self.owner.subject))
        self.assertTrue(first.allow(self.owner.issuer, self.owner.subject))
        with self.assertRaises(PermissionError):
            second.allow(self.owner.issuer, self.owner.subject)

    def test_fail_closed_when_database_unavailable(self):
        def unavailable():
            raise OSError("database unavailable")

        limiter = PostgresIdentityLimiter(unavailable)
        with self.assertRaises(PermissionError):
            limiter.allow(self.owner.issuer, self.owner.subject)


if __name__ == "__main__":
    unittest.main()
