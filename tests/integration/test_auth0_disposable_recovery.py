"""Real disposable PostgreSQL 16 Auth0 session, replay and crash-safety acceptance.

Only run with ALPHA_DISPOSABLE_PG_DSN from the GitHub Actions service container.
Never point this suite at a persistent or hosted database.
"""
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from deployment.postgres_oauth_state import PostgresOAuthStateStore, SCHEMA as OAUTH_SCHEMA
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions, SCHEMA as SESSION_SCHEMA


@unittest.skipUnless(os.getenv("ALPHA_DISPOSABLE_PG_DSN"), "disposable CI PostgreSQL required")
class DisposableAuth0RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.dsn = os.environ["ALPHA_DISPOSABLE_PG_DSN"]
        cls.connect = staticmethod(lambda: psycopg.connect(cls.dsn))
        with cls.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(OAUTH_SCHEMA)
                cur.execute(SESSION_SCHEMA)

    def setUp(self):
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE public.alpha_oauth_transactions, public.alpha_oidc_sessions")

    def test_single_use_across_reopened_connections(self):
        store = PostgresOAuthStateStore(self.connect)
        state = "A" * 48
        expires = int(datetime.now(timezone.utc).timestamp()) + 120
        store.put(state, {"expires": expires, "nonce": "n"})
        self.assertEqual(store.consume(state)["nonce"], "n")
        with self.assertRaises(PermissionError):
            PostgresOAuthStateStore(self.connect).consume(state)

    def test_concurrent_state_consumption_exactly_once(self):
        state = "B" * 48
        store = PostgresOAuthStateStore(self.connect)
        store.put(state, {"expires": int(datetime.now(timezone.utc).timestamp()) + 120})
        gate = threading.Barrier(6)
        def consume(_):
            gate.wait(timeout=10)
            try:
                return bool(PostgresOAuthStateStore(self.connect).consume(state))
            except PermissionError:
                return False
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(consume, range(6)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 5)

    def test_expired_state_rejected(self):
        state = "C" * 48
        store = PostgresOAuthStateStore(self.connect)
        store.put(state, {"expires": int(datetime.now(timezone.utc).timestamp()) - 5})
        with self.assertRaises(PermissionError):
            store.consume(state)

    def test_session_expiry_revocation_and_account_isolation(self):
        clock = [datetime(2030, 1, 1, tzinfo=timezone.utc)]
        sessions = PostgresOpaqueSessions(self.connect, clock=lambda: clock[0])
        a = sessions.create("auth0|alice", "https://issuer.example/")
        b = sessions.create("auth0|bob", "https://issuer.example/")
        self.assertNotEqual(sessions.resolve_owner(a), sessions.resolve_owner(b))
        self.assertEqual(sessions.resolve_owner(a), sessions._owner("auth0|alice", "https://issuer.example/"))
        sessions.revoke(a)
        with self.assertRaises(PermissionError):
            sessions.resolve_owner(a)
        self.assertEqual(sessions.resolve_owner(b), sessions._owner("auth0|bob", "https://issuer.example/"))
        clock[0] += timedelta(minutes=31)
        with self.assertRaises(PermissionError):
            sessions.resolve_owner(b)
        with self.assertRaises(PermissionError):
            sessions.resolve_owner("forged-token-value-" + "z" * 32)

    def test_rollback_preserves_oauth_state(self):
        store = PostgresOAuthStateStore(self.connect)
        state = "D" * 48
        store.put(state, {"expires": int(datetime.now(timezone.utc).timestamp()) + 120})
        try:
            with self.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM public.alpha_oauth_transactions WHERE state_hash=%s",
                                (store._hash(state),))
                    raise RuntimeError("simulated interrupted transaction")
        except RuntimeError:
            pass
        self.assertIsNotNone(store.consume(state))

    def test_committed_revocation_survives_new_connection(self):
        sessions = PostgresOpaqueSessions(self.connect)
        token = sessions.create("auth0|alice", "https://issuer.example/")
        sessions.revoke(token)
        with self.assertRaises(PermissionError):
            PostgresOpaqueSessions(self.connect).resolve_owner(token)


if __name__ == "__main__":
    unittest.main()
