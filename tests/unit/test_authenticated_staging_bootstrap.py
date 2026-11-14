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


if __name__ == "__main__":
    unittest.main()
