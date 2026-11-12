import unittest
from alpha_lab.research.oidc_session_foundation import SessionRegistry


class OIDCSessionFoundationTests(unittest.TestCase):
    def setUp(self):
        self.clock = [1000]
        self.registry = SessionRegistry(now=lambda: self.clock[0])

    def test_nonce_state_and_one_time_consumption(self):
        state, nonce, verifier = self.registry.begin()
        self.assertGreaterEqual(len(verifier), 64)
        self.assertEqual(self.registry.consume(state, nonce), verifier)
        with self.assertRaises(PermissionError):
            self.registry.consume(state, nonce)

    def test_wrong_nonce_consumes_state(self):
        state, nonce, _ = self.registry.begin()
        with self.assertRaises(PermissionError):
            self.registry.consume(state, "forged")
        with self.assertRaises(PermissionError):
            self.registry.consume(state, nonce)

    def test_expired_state_rejected(self):
        state, nonce, _ = self.registry.begin()
        self.clock[0] += 301
        with self.assertRaises(PermissionError):
            self.registry.consume(state, nonce)

    def test_session_expiry_revocation_and_isolation(self):
        alice = self.registry.create_session(subject="alice", issuer="issuer", expires_at=1050)
        bob = self.registry.create_session(subject="bob", issuer="issuer", expires_at=1050)
        self.assertEqual(self.registry.authenticate(alice).subject, "alice")
        self.assertEqual(self.registry.authenticate(bob).subject, "bob")
        self.registry.revoke(alice)
        with self.assertRaises(PermissionError):
            self.registry.authenticate(alice)
        self.assertEqual(self.registry.authenticate(bob).subject, "bob")
        self.clock[0] = 1050
        with self.assertRaises(PermissionError):
            self.registry.authenticate(bob)

    def test_invalid_session_lifetime(self):
        for expiry in (1000, 4601, True, "1050"):
            with self.subTest(expiry=expiry), self.assertRaises(PermissionError):
                self.registry.create_session(subject="alice", issuer="issuer", expires_at=expiry)

if __name__ == "__main__":
    unittest.main()
