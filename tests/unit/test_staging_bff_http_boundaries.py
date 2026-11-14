"""Additional fail-closed HTTP boundary tests for staging BFF.

No Auth0, PostgreSQL, network, or Render resources are accessed.
"""
import unittest
from deployment.staging_authenticated_bff import StagingResearchBFF


class NeverCall:
    def __getattr__(self, name):
        raise AssertionError("unexpected dependency access: " + name)


class HttpBoundaryTests(unittest.TestCase):
    def setUp(self):
        sentinel = NeverCall()
        self.app = StagingResearchBFF(
            sentinel, sentinel, sentinel, sentinel,
            origin="https://staging.example")

    def request(self, path, method="GET", **kwargs):
        responses = []
        env = {"PATH_INFO": path, "REQUEST_METHOD": method, **kwargs}
        body = b"".join(self.app(env, lambda status, headers: responses.append((status, headers))))
        return responses[0][0], dict(responses[0][1]), body

    def test_trading_endpoints_not_exposed(self):
        for path in ("/api/v1/trade", "/api/v1/orders", "/api/v1/execute",
                     "/api/v1/broker", "/api/v1/paper/orders"):
            for method in ("GET", "POST", "PUT", "DELETE"):
                with self.subTest(path=path, method=method):
                    status, _, _ = self.request(path, method)
                    self.assertEqual(status, "404 Not Found")

    def test_unauthenticated_read_only_endpoints_denied(self):
        for path in ("/api/v1/research/runs", "/api/v1/research/summary"):
            status, headers, _ = self.request(path)
            self.assertEqual(status, "401 Unauthorized")
            self.assertEqual(headers["Cache-Control"], "no-store")

    def test_callback_rejects_missing_duplicate_and_unbound_state(self):
        for query in ("", "code=x", "state=y", "code=x&state=y",
                      "code=x&code=z&state=y", "code=x&state=y&error=z"):
            with self.subTest(query=query):
                status, _, _ = self.request("/auth/callback", QUERY_STRING=query)
                self.assertEqual(status, "401 Unauthorized")

    def test_logout_requires_exact_origin(self):
        for origin in ("", "http://staging.example", "https://evil.example",
                       "https://staging.example.evil.example"):
            status, _, _ = self.request("/auth/logout", "POST", HTTP_ORIGIN=origin)
            self.assertEqual(status, "403 Forbidden")

    def test_health_check_does_not_enable_trading(self):
        status, headers, body = self.request("/healthz")
        self.assertEqual(status, "200 OK")
        self.assertIn(b'"trading":"disabled"', body)
        self.assertEqual(headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
