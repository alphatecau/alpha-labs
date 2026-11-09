import unittest
from unittest.mock import Mock
from alpha_lab.research.authenticated_staging_wsgi import AuthenticatedReadOnlyStaging
from alpha_lab.research.oidc_browser_wsgi import OIDCBrowserWSGI
from alpha_lab.research.oidc_postgres_store import PostgresOIDCStore
from alpha_lab.research.postgres_paper_security import PostgresPaperOwnership, PostgresIdentityLimiter


class AuthenticatedStagingBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.auth = object.__new__(OIDCBrowserWSGI)
        self.sessions = PostgresOIDCStore(lambda: None)
        self.auth.store = self.sessions
        self.auth.origin = "https://staging.example.com"
        self.auth.__dict__["called"] = False
        self.ownership = PostgresPaperOwnership(lambda: None)
        self.limiter = PostgresIdentityLimiter(lambda: None)
        self.app = AuthenticatedReadOnlyStaging(
            auth=self.auth, sessions=self.sessions, accounts=Mock(),
            ownership=self.ownership, limiter=self.limiter,
            expected_origin="https://staging.example.com",
            trusted_peer_cidrs=["10.12.0.0/24"])

    def request(self, path, **extra):
        seen = {}
        def start(status, headers):
            seen["status"] = status
        env = {"REMOTE_ADDR": "10.12.0.3", "HTTP_HOST": "staging.example.com",
               "PATH_INFO": path, "REQUEST_METHOD": "GET", **extra}
        body = b"".join(self.app(env, start))
        return seen["status"], body

    def test_unknown_and_trading_routes_rejected(self):
        for path in ("/", "/api/v1/trade", "/api/v1/order", "/api/v1/copy"):
            with self.subTest(path=path):
                status, _ = self.request(path)
                self.assertEqual(status, "404 Not Found")

    def test_untrusted_peer_and_forwarded_headers_rejected(self):
        for env in ({"REMOTE_ADDR": "203.0.113.4"},
                    {"HTTP_X_FORWARDED_PROTO": "https"},
                    {"HTTP_FORWARDED": "proto=https"},
                    {"HTTP_HOST": "attacker.example"}):
            with self.subTest(env=env):
                status, body = self.request("/auth/login", **env)
                self.assertEqual(status, "403 Forbidden")
                self.assertIn(b"ingress_rejected", body)

    def test_no_credentials_or_in_memory_session_fallback(self):
        with self.assertRaises(ValueError):
            AuthenticatedReadOnlyStaging(
                auth=self.auth, sessions=object(), accounts=Mock(),
                ownership=self.ownership, limiter=self.limiter,
                expected_origin="https://staging.example.com",
                trusted_peer_cidrs=["10.12.0.0/24"])
        with self.assertRaises(ValueError):
            AuthenticatedReadOnlyStaging(
                auth=self.auth, sessions=self.sessions, accounts=Mock(),
                ownership=self.ownership, limiter=self.limiter,
                expected_origin="https://staging.example.com",
                trusted_peer_cidrs=[])


if __name__ == "__main__":
    unittest.main()
