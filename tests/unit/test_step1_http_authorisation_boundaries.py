"""Step 1: exercise actual HTTP handlers, not just source strings."""
import http.client
import json
import threading
import unittest

from tools.local_research_server import create_server


class HttpAuthorisationBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def request(self, method, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            conn.request(method, path)
            response = conn.getresponse()
            body = response.read()
            return response.status, dict(response.getheaders()), body
        finally:
            conn.close()

    def test_no_execution_routes_for_all_common_mutation_verbs(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                status, _, _ = self.request(method, "/api/v1/trade/execute")
                self.assertNotEqual(status, 200)

    def test_unknown_api_route_is_not_static_fallback(self):
        status, _, _ = self.request("GET", "/api/v1/trade/execute")
        self.assertEqual(status, 404)

    def test_research_api_refuses_query_parameters(self):
        status, _, _ = self.request("GET", "/api/v1/research/solusd?promotion_authorised=true")
        self.assertEqual(status, 400)

    def test_unavailable_data_fails_closed(self):
        status, _, body = self.request("GET", "/api/v1/research/solusd")
        self.assertNotEqual(status, 200)
        self.assertNotIn(b'"promotion_authorised":true', body)


if __name__ == "__main__":
    unittest.main()
