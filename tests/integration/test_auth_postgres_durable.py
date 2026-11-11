"""Disposable PostgreSQL 16 acceptance for OAuth state and opaque sessions.

Never uses Render/staging DB; refuses DSNs without alpha_rls_test.
"""
import hashlib
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
import psycopg
from disposable_pg_guard import require_disposable_ci_database
from deployment.postgres_pkce_state_store import PostgresPKCEStateStore
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions

@unittest.skipUnless(os.getenv("ALPHA_TEST_PG_DSN"), "disposable PostgreSQL only")
class DurableAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.dsn=os.environ["ALPHA_TEST_PG_DSN"]
        require_disposable_ci_database(self.dsn)
        self.admin=psycopg.connect(self.dsn,autocommit=True)
        self.admin.execute("CREATE TABLE alpha_oauth_state(digest char(64) PRIMARY KEY,payload jsonb NOT NULL,expires_at timestamptz NOT NULL)")
        self.admin.execute("CREATE TABLE alpha_oidc_sessions(session_hash text PRIMARY KEY,owner_id text NOT NULL,expires_at timestamptz NOT NULL)")
        self.connect=lambda: psycopg.connect(self.dsn)
    def tearDown(self):
        self.admin.execute("DROP TABLE IF EXISTS alpha_oauth_state")
        self.admin.execute("DROP TABLE IF EXISTS alpha_oidc_sessions")
        self.admin.close()
    def test_state_consumed_exactly_once(self):
        store=PostgresPKCEStateStore(self.connect)
        digest=hashlib.sha256(b"synthetic-state").hexdigest()
        record={"nonce":"synthetic-nonce","verifier":"synthetic-pkce","created_at":int(store.clock())}
        store.put(digest,record,300)
        self.assertEqual(store.consume(digest),record)
        self.assertIsNone(store.consume(digest))
    def test_session_owner_expiry_and_revocation(self):
        store=PostgresOpaqueSessions(self.connect)
        token=store.create("alice","https://tenant.auth0.com/")
        owner=store.resolve_owner(token)
        self.assertEqual(owner,store._owner("alice","https://tenant.auth0.com/"))
        self.assertNotEqual(owner,store._owner("bob","https://tenant.auth0.com/"))
        store.revoke(token)
        with self.assertRaises(PermissionError):
            store.resolve_owner(token)
        with self.assertRaises(PermissionError):
            store.resolve_owner("forged")
    def test_expired_pkce_denied(self):
        store=PostgresPKCEStateStore(self.connect,clock=lambda:1000)
        digest=hashlib.sha256(b"expired").hexdigest()
        store.put(digest,{"nonce":"n","verifier":"v","created_at":1000},1)
        later=PostgresPKCEStateStore(self.connect,clock=lambda:1002)
        self.assertIsNone(later.consume(digest))

    def test_concurrent_instances_consume_state_once(self):
        store = PostgresPKCEStateStore(self.connect)
        digest = hashlib.sha256(b"concurrent-synthetic-state").hexdigest()
        record = {"nonce": "synthetic", "verifier": "synthetic", "created_at": int(store.clock())}
        store.put(digest, record, 300)
        def consume(_):
            return PostgresPKCEStateStore(self.connect).consume(digest)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(consume, range(8)))
        self.assertEqual(sum(r == record for r in results), 1)
        self.assertEqual(sum(r is None for r in results), 7)

if __name__=="__main__": unittest.main()
