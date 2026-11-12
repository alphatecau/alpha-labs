"""Offline adversarial Auth0 session and credential broker tests."""
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit
from deployment.auth0_login_flow import Auth0LoginFlow
from deployment.auth0_session_controller import Auth0SessionController
from deployment.sqlite_pkce_state_store import SQLitePKCEStateStore
from deployment.tenant_credential_broker import TenantCredentialBroker


class FakeSessions:
    def __init__(self): self.created = []
    def create(self, subject, issuer):
        self.created.append((subject, issuer))
        return "opaque-test-session"


class FakeOwner:
    def __init__(self, allow=True): self.allow = allow
    def require(self, principal, slot):
        if not self.allow: raise PermissionError("not provisioned")


class Auth0AdversarialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLitePKCEStateStore(self.tmp.name + "/pkce.sqlite", clock=lambda: 1000)
        self.flow = Auth0LoginFlow(issuer="https://tenant.auth0.com", client_id="client",
                 redirect_uri="https://dashboard.example/callback", state_store=self.store,
                 clock=lambda: 1000)
        self.sessions = FakeSessions()
        self.owner = FakeOwner()
        self.nonce = None
        self.controller = Auth0SessionController(
            self.flow, lambda token: {"verified": True, "issuer": self.flow.issuer,
                "subject": "alice", "nonce": self.nonce},
            self.sessions, self.owner,
            lambda **kwargs: kwargs,
            exchange=lambda code, verifier: "signed-test-id-token")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def begin(self):
        params = parse_qs(urlsplit(self.flow.begin()).query)
        self.nonce = params["nonce"][0]
        return params["state"][0]

    def test_success_cookie_and_replay(self):
        state = self.begin()
        cookie = self.controller.complete(state, "code")
        self.assertIn("Secure; HttpOnly; SameSite=Lax", cookie)
        self.assertEqual(self.sessions.created, [("alice", self.flow.issuer)])
        with self.assertRaises(PermissionError):
            self.controller.complete(state, "code")

    def test_wrong_nonce_and_unauthorised_owner(self):
        state = self.begin()
        self.nonce = "forged"
        with self.assertRaises(PermissionError):
            self.controller.complete(state, "code")
        self.assertEqual(self.sessions.created, [])
        state = self.begin()
        self.owner.allow = False
        with self.assertRaises(PermissionError):
            self.controller.complete(state, "code")
        self.assertEqual(self.sessions.created, [])

    def test_failed_exchange_consumes_state(self):
        state = self.begin()
        self.controller.exchange = lambda code, verifier: (_ for _ in ()).throw(RuntimeError("exchange failed"))
        with self.assertRaises(RuntimeError):
            self.controller.complete(state, "code")
        with self.assertRaises(PermissionError):
            self.controller.complete(state, "code")

    def test_broker_rejects_unprovisioned_and_bad_role(self):
        broker = TenantCredentialBroker(lambda owner: None, lambda **kwargs: self.fail("unexpected connect"))
        with self.assertRaises(PermissionError):
            with broker("unknown"): pass
        broker = TenantCredentialBroker(
            lambda owner: {"host":"db.example", "port":5432, "dbname":"research",
                           "user":"postgres", "password":"test-only"},
            lambda **kwargs: self.fail("unsafe role connected"))
        with self.assertRaises(PermissionError):
            with broker("oidc_" + "a" * 64): pass


if __name__ == "__main__":
    unittest.main()
