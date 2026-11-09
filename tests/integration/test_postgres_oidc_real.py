"""Real PostgreSQL OIDC session, replay and migration acceptance tests (CI only)."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

try:
    import psycopg
except ImportError:
    psycopg = None

from alpha_lab.research.oidc_postgres_store import PostgresOIDCStore
from alpha_lab.research.postgres_oidc_migration import apply_oidc_schema, verify_oidc_schema


@unittest.skipUnless(psycopg is not None and os.getenv("ALPHA_TEST_POSTGRES_DSN"),
                     "Requires isolated PostgreSQL CI service")
class RealOIDCPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["ALPHA_TEST_POSTGRES_DSN"]
        cls.connect = staticmethod(lambda: psycopg.connect(cls.dsn))
        apply_oidc_schema(cls.connect)

    def setUp(self):
        with self.connect() as conn:
            conn.execute("TRUNCATE oidc_pending, oidc_sessions")
        self.store = PostgresOIDCStore(self.connect, now=lambda: 1000000)

    def test_migration_idempotent_and_verified(self):
        apply_oidc_schema(self.connect)
        self.assertTrue(verify_oidc_schema(self.connect))

    def test_session_persists_between_connections_and_revokes(self):
        sid = self.store.create("subject-A", "https://issuer.example/", ttl=1800)
        other = PostgresOIDCStore(self.connect, now=lambda: 1000001)
        self.assertEqual(other.authenticate(sid), ("subject-A", "https://issuer.example/"))
        other.revoke(sid)
        with self.assertRaises(PermissionError):
            self.store.authenticate(sid)

    def test_expiry_and_purge(self):
        sid = self.store.create("subject-A", "https://issuer.example/", ttl=10)
        expired = PostgresOIDCStore(self.connect, now=lambda: 1000010)
        with self.assertRaises(PermissionError):
            expired.authenticate(sid)
        expired.purge_expired()
        with self.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM oidc_sessions").fetchone()[0], 0)

    def test_state_nonce_one_time_and_wrong_nonce(self):
        state, nonce, verifier = self.store.begin()
        with self.assertRaises(PermissionError):
            self.store.consume(state, "x" * 64)
        with self.assertRaises(PermissionError):
            self.store.consume(state, nonce)
        state, nonce, verifier = self.store.begin()
        self.assertEqual(self.store.consume(state, nonce), verifier)
        with self.assertRaises(PermissionError):
            self.store.consume(state, nonce)

    def test_concurrent_state_consume_single_winner(self):
        state, nonce, verifier = self.store.begin()
        barrier = Barrier(12)
        def consume(_):
            barrier.wait(timeout=15)
            try:
                return self.store.consume(state, nonce)
            except PermissionError:
                return None
        with ThreadPoolExecutor(max_workers=12) as pool:
            outcomes = list(pool.map(consume, range(12)))
        self.assertEqual(outcomes.count(verifier), 1)
        self.assertEqual(outcomes.count(None), 11)

    def test_expired_pending_state_rejected(self):
        state, nonce, _ = self.store.begin()
        expired = PostgresOIDCStore(self.connect, now=lambda: 1000300)
        with self.assertRaises(PermissionError):
            expired.consume(state, nonce)


if __name__ == "__main__":
    unittest.main()
