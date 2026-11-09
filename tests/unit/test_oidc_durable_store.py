import tempfile
import unittest
from pathlib import Path

from alpha_lab.research.oidc_durable_store import DurableOIDCStore


class DurableStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "oidc.sqlite")
        self.clock = [1000]
        self.store = DurableOIDCStore(self.path, now=lambda: self.clock[0])

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_persistence_and_single_use(self):
        state, nonce, verifier = self.store.begin()
        self.store.close()
        self.store = DurableOIDCStore(self.path, now=lambda: self.clock[0])
        self.assertEqual(self.store.consume(state, nonce), verifier)
        with self.assertRaises(PermissionError):
            self.store.consume(state, nonce)

    def test_wrong_nonce_consumes_transaction(self):
        state, nonce, _ = self.store.begin()
        with self.assertRaises(PermissionError):
            self.store.consume(state, "x" * 30)
        with self.assertRaises(PermissionError):
            self.store.consume(state, nonce)

    def test_expired_login_and_session(self):
        state, nonce, _ = self.store.begin()
        self.clock[0] = 1301
        with self.assertRaises(PermissionError):
            self.store.consume(state, nonce)
        sid = self.store.create("owner", "issuer", ttl=60)
        self.assertEqual(self.store.authenticate(sid), ("owner", "issuer"))
        self.clock[0] = 1361
        with self.assertRaises(PermissionError):
            self.store.authenticate(sid)

    def test_revoke_persists(self):
        sid = self.store.create("owner", "issuer")
        self.store.revoke(sid)
        self.store.close()
        self.store = DurableOIDCStore(self.path, now=lambda: self.clock[0])
        with self.assertRaises(PermissionError):
            self.store.authenticate(sid)

    def test_distinct_sessions(self):
        a = self.store.create("alice", "issuer")
        b = self.store.create("bob", "issuer")
        self.assertNotEqual(self.store.authenticate(a), self.store.authenticate(b))
        with self.assertRaises(PermissionError):
            self.store.authenticate("forgedcredential" * 3)


if __name__ == "__main__":
    unittest.main()
