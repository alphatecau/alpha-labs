"""Offline adversarial tests of OAuth PKCE and one-time callback handling."""
import unittest
from urllib.parse import parse_qs, urlsplit

from deployment.auth0_pkce_callback import Auth0PKCEFlow, Auth0CallbackController


class MemoryAtomicStore:
    def __init__(self):
        self.items = {}

    def put(self, state, payload):
        self.items[state] = payload

    def consume(self, state):
        if state not in self.items:
            raise PermissionError("replayed state")
        return self.items.pop(state)


class Sessions:
    def __init__(self):
        self.created = []

    def create(self, subject, issuer):
        self.created.append((subject, issuer))
        return "s" * 48


class TokenVerifier:
    def verify(self, token, *, expected_nonce):
        if token != "signed-id-token" or not expected_nonce:
            raise PermissionError("invalid token")
        from alpha_lab.research.paper_account_service import VerifiedPrincipal
        return VerifiedPrincipal("auth0|alice", "https://alpha-labs-dev.au.auth0.com/")


class CallbackTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryAtomicStore()
        self.flow = Auth0PKCEFlow(
            issuer="https://alpha-labs-dev.au.auth0.com/",
            client_id="test-client",
            redirect_uri="https://isolated.example/auth/callback",
            state_store=self.store,
            clock=lambda: 100,
        )
        self.sessions = Sessions()
        self.exchanges = []
        def exchange(**kwargs):
            self.exchanges.append(kwargs)
            return {"id_token": "signed-id-token"}
        self.controller = Auth0CallbackController(
            flow=self.flow, exchange_code=exchange,
            token_verifier=TokenVerifier(), sessions=self.sessions,
            authorise_principal=lambda principal: principal.subject == "auth0|alice",
        )

    def begin(self):
        query = parse_qs(urlsplit(self.flow.begin()).query)
        return query, query["state"][0]

    def test_pkce_nonce_and_exact_redirect(self):
        query, state = self.begin()
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["redirect_uri"], ["https://isolated.example/auth/callback"])
        self.assertEqual(query["nonce"], [self.store.items[state]["nonce"]])
        self.assertNotEqual(query["code_challenge"][0], self.store.items[state]["verifier"])

    def test_success_then_replay_denied(self):
        _, state = self.begin()
        cookie = self.controller.complete(state, "test-code")
        self.assertIn("Secure; HttpOnly; SameSite=Lax", cookie)
        self.assertEqual(len(self.sessions.created), 1)
        with self.assertRaises(PermissionError):
            self.controller.complete(state, "test-code")
        self.assertEqual(len(self.exchanges), 1)

    def test_invalid_token_consumes_state(self):
        _, state = self.begin()
        self.controller.token_verifier = TokenVerifier()
        self.controller.exchange_code = lambda **kwargs: {"id_token": "forged"}
        with self.assertRaises(PermissionError):
            self.controller.complete(state, "code")
        with self.assertRaises(PermissionError):
            self.controller.complete(state, "code")

    def test_expired_state_denied_without_exchange(self):
        _, state = self.begin()
        self.store.items[state]["expires"] = 99
        with self.assertRaises(PermissionError):
            self.controller.complete(state, "code")
        self.assertEqual(self.exchanges, [])

    def test_unprovisioned_denied_without_session(self):
        _, state = self.begin()
        self.controller.authorise_principal = lambda principal: False
        with self.assertRaises(PermissionError):
            self.controller.complete(state, "code")
        self.assertEqual(self.sessions.created, [])


if __name__ == "__main__":
    unittest.main()
