"""Adversarial fail-closed acceptance for the existing staging WSGI BFF.

These tests use no real Auth0 tenant, credentials or database.
"""
import unittest
from deployment.staging_authenticated_bff import StagingResearchBFF


class ExplodingDependency:
    def __getattr__(self, name):
        raise AssertionError("unauthorised dependency reached: " + name)


class StagingBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.app = StagingResearchBFF(
            ExplodingDependency(), ExplodingDependency(),
            ExplodingDependency(), ExplodingDependency(),
            origin="https://staging.example"
        )

    def request(self, path, method="GET", **extra):
        captured = {}
        def start(status, headers):
            captured["status"], captured["headers"] = status, headers
        body = b"".join(self.app({
            "PATH_INFO": path, "REQUEST_METHOD": method, **extra
        }, start))
        return captured["status"], dict(captured["headers"]), body

    def test_trading_routes_denied_without_touching_dependencies(self):
        for path in (
            "/api/v1/trade", "/api/v1/trading/orders",
            "/api/v1/orders", "/api/v1/execute", "/broker",
            "/api/v1/paper/orders", "/api/v1/research/promote"
        ):
            with self.subTest(path=path):
                status, _, _ = self.request(path, "POST")
                self.assertEqual(status, "404 Not Found")

    def test_research_requires_session(self):
        for path in ("/api/v1/research/runs", "/api/v1/research/summary"):
            with self.subTest(path=path):
                status, _, _ = self.request(path)
                self.assertEqual(status, "401 Unauthorized")

    def test_logout_rejects_cross_origin(self):
        status, _, _ = self.request(
            "/auth/logout", "POST", HTTP_ORIGIN="https://attacker.example")
        self.assertEqual(status, "403 Forbidden")

    def test_callback_requires_matching_browser_state(self):
        status, _, _ = self.request(
            "/auth/callback", QUERY_STRING="code=synthetic&state=synthetic")
        self.assertEqual(status, "401 Unauthorized")

    def test_health_does_not_claim_trading_enabled(self):
        status, headers, body = self.request("/healthz")
        self.assertEqual(status, "200 OK")
        self.assertIn(b'"trading":"disabled"', body)
        self.assertEqual(headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
