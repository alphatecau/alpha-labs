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
from alpha_lab.research.postgres_paper_security import (
    PostgresPaperOwnership, PostgresIdentityLimiter, SCHEMA,
)


@unittest.skipUnless(psycopg is not None and os.getenv("ALPHA_TEST_POSTGRES_DSN"),
                     "Requires explicit isolated PostgreSQL CI service")
class RealPostgresSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["ALPHA_TEST_POSTGRES_DSN"]
        cls.connect = staticmethod(lambda: psycopg.connect(cls.dsn))
        with cls.connect() as conn:
            conn.execute(SCHEMA)

    def setUp(self):
        with self.connect() as conn:
            conn.execute("TRUNCATE TABLE paper_ownership, identity_rate_limit")
        self.owner = VerifiedPrincipal(subject="integration_owner", issuer="https://test-issuer.example/")

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
        limiter = PostgresIdentityLimiter(self.connect, limit=limit, window=60, clock=lambda: 120)
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
        self.assertEqual(count, workers)

    def test_fail_closed_when_database_unavailable(self):
        def unavailable():
            raise OSError("database unavailable")
        limiter = PostgresIdentityLimiter(unavailable)
        with self.assertRaises(PermissionError):
            limiter.allow(self.owner.issuer, self.owner.subject)


if __name__ == "__main__":
    unittest.main()
