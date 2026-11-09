import unittest
from deployment.staging_probe import application


class StagingProbeTests(unittest.TestCase):
    def invoke(self, path, method="GET"):
        seen = {}
        def start(status, headers):
            seen["status"], seen["headers"] = status, dict(headers)
        body = b"".join(application({"PATH_INFO": path, "REQUEST_METHOD": method}, start))
        return seen, body

    def test_healthz_reports_no_trading(self):
        meta, body = self.invoke("/healthz")
        self.assertEqual(meta["status"], "200 OK")
        self.assertIn(b'"trading": "disabled"', body)
        self.assertIn(b'"mode": "research_only"', body)

    def test_all_other_routes_unavailable(self):
        for path, method in [("/", "GET"), ("/auth/login", "GET"),
                             ("/api/v1/trade", "POST"), ("/healthz", "POST")]:
            with self.subTest(path=path, method=method):
                meta, _ = self.invoke(path, method)
                self.assertEqual(meta["status"], "404 Not Found")


if __name__ == "__main__":
    unittest.main()
