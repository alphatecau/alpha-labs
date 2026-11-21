"""Contract checks for the deliberately read-only Render Level 3 probe.

No broker credentials, external network, paid services, or writes required.
"""
import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from deployment.level3_cloud_probe import Handler


class Level3CloudProbeContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def request(self, method, path):
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            conn.request(method, path, body=b"{}", headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_health_only_proves_process_alive(self):
        status, headers, body = self.request("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["alive"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("ready", json.loads(body))

    def test_readiness_fails_closed(self):
        status, headers, body = self.request("GET", "/readyz")
        self.assertEqual(status, 503)
        self.assertIs(json.loads(body)["ready"], False)
        self.assertIn("custody", json.loads(body)["reason"])
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_no_write_endpoint(self):
        for path in ("/", "/readyz", "/healthz", "/write", "/mcp"):
            with self.subTest(path=path):
                status, _, _ = self.request("POST", path)
                self.assertEqual(status, 405)

    def test_unknown_get_not_exposed(self):
        for path in ("/", "/mcp", "/tools/list", "/healthz?verbose=1"):
            with self.subTest(path=path):
                status, _, _ = self.request("GET", path)
                self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
