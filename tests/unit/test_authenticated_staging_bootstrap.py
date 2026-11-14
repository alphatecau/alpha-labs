"""Fail-closed bootstrap tests; synthetic dependencies only."""
import unittest
from deployment.authenticated_staging_bootstrap import build_authenticated_application


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "AUTH0_ISSUER": "https://example.auth0.com",
            "AUTH0_CLIENT_ID": "synthetic-client",
            "AUTH0_CALLBACK_URL": "https://staging.example/auth/callback",
            "ALPHA_BFF_ORIGIN": "https://staging.example",
            "AUTH0_CLIENT_SECRET": "synthetic-secret-not-real",
        }
        self.connect = lambda **kwargs: None

    def test_missing_ownership_denied_before_verifier_fetch(self):
        with self.assertRaises(ValueError):
            build_authenticated_application(
                environ=self.env, ownership=None, principal_factory=lambda **k: k,
                state_connect=self.connect, session_connect=self.connect,
                tenant_connect=self.connect,
                verifier_factory=lambda *a: self.fail("unexpected verifier fetch"))

    def test_missing_connection_denied_before_verifier_fetch(self):
        class Ownership:
            def require_owner_id(self, owner, account):
                return True
            def require(self, principal, scope):
                return None
        with self.assertRaises(ValueError):
            build_authenticated_application(
                environ=self.env, ownership=Ownership(), principal_factory=lambda **k: k,
                state_connect=None, session_connect=self.connect,
                tenant_connect=self.connect,
                verifier_factory=lambda *a: self.fail("unexpected verifier fetch"))

    def test_verified_dependencies_construct_wsgi_without_network(self):
        class Ownership:
            def require_owner_id(self, owner, account):
                return True
            def require(self, principal, scope):
                return None
        app = build_authenticated_application(
            environ=self.env, ownership=Ownership(), principal_factory=lambda **k: k,
            state_connect=self.connect, session_connect=self.connect,
            tenant_connect=self.connect, verifier_factory=lambda *a: lambda token: None)
        captured = []
        body = b"".join(app({"PATH_INFO": "/healthz", "REQUEST_METHOD": "GET"},
                            lambda status, headers: captured.append(status)))
        self.assertEqual(captured, ["200 OK"])
        self.assertIn(b'"trading":"disabled"', body)


    def test_missing_confidential_secret_fails_closed(self):
        class Ownership:
            def require_owner_id(self, owner, account):
                return True
            def require(self, principal, scope):
                return None
        env = dict(self.env)
        env.pop("AUTH0_CLIENT_SECRET")
        with self.assertRaises(ValueError):
            build_authenticated_application(
                environ=env, ownership=Ownership(), principal_factory=lambda **k: k,
                state_connect=self.connect, session_connect=self.connect,
                tenant_connect=self.connect, verifier_factory=lambda *a: lambda token: None)

    def test_untrusted_verifier_fails_closed(self):
        class Ownership:
            def require_owner_id(self, owner, account):
                return True
            def require(self, principal, scope):
                return None
        with self.assertRaises(ValueError):
            build_authenticated_application(
                environ=self.env, ownership=Ownership(), principal_factory=lambda **k: k,
                state_connect=self.connect, session_connect=self.connect,
                tenant_connect=self.connect, verifier_factory=lambda *a: None)

    def test_invalid_principal_factory_fails_before_verifier(self):
        class Ownership:
            def require_owner_id(self, owner, account):
                return True
            def require(self, principal, scope):
                return None
        with self.assertRaises(ValueError):
            build_authenticated_application(
                environ=self.env, ownership=Ownership(), principal_factory=None,
                state_connect=self.connect, session_connect=self.connect,
                tenant_connect=self.connect,
                verifier_factory=lambda *a: self.fail("unexpected verifier fetch"))

    def test_authenticated_routes_not_public_without_session(self):
        class Ownership:
            def require_owner_id(self, owner, account):
                return True
            def require(self, principal, scope):
                return None
        app = build_authenticated_application(
            environ=self.env, ownership=Ownership(), principal_factory=lambda **k: k,
            state_connect=self.connect, session_connect=self.connect,
            tenant_connect=self.connect, verifier_factory=lambda *a: lambda token: None)
        for path in ("/api/v1/research/runs", "/api/v1/research/summary"):
            with self.subTest(path=path):
                status = []
                app({"PATH_INFO": path, "REQUEST_METHOD": "GET"},
                    lambda code, headers: status.append(code))
                self.assertEqual(status, ["401 Unauthorized"])
        for path in ("/api/v1/trade", "/api/v1/orders", "/api/v1/execute"):
            with self.subTest(path=path):
                status = []
                app({"PATH_INFO": path, "REQUEST_METHOD": "POST"},
                    lambda code, headers: status.append(code))
                self.assertEqual(status, ["404 Not Found"])


if __name__ == "__main__":
    unittest.main()
