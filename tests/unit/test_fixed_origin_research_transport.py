"""Offline tests for fixed-origin BFF transport; no network requests."""
import io
import unittest
from unittest.mock import Mock
from email.message import Message
from deployment.fixed_origin_research_transport import FixedOriginResearchTransport


class FakeResponse:
    status = 200
    headers = Message()
    headers["Content-Type"] = "application/json"
    def __init__(self, body=b'{"status":"verified_source"}'):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit):
        return self.body[:limit]


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.t = FixedOriginResearchTransport("https://research.internal.example")
        self.headers = {"Authorization": "Bearer test-signed-assertion", "Accept": "application/json"}

    def test_https_origin_required_and_no_userinfo(self):
        for origin in ("http://example.com", "https://user:pass@example.com",
                       "https://example.com/path", "https://example.com/?token=secret"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                FixedOriginResearchTransport(origin)

    def test_fixed_path_and_headers(self):
        for path in ("https://evil.example/", "//evil.example/", "/api/v1/research/write", "/api/v1/research/runs?owner=b"):
            with self.subTest(path=path), self.assertRaises(PermissionError):
                self.t(path, self.headers)
        with self.assertRaises(PermissionError):
            self.t("/api/v1/research/runs", {**self.headers, "Cookie": "session=secret"})

    def test_get_uses_fixed_origin_and_timeout(self):
        opened = []
        def fake_open(request, timeout):
            opened.append((request.full_url, request.get_method(), timeout, request.headers))
            return FakeResponse()
        self.t._opener.open = fake_open
        result = self.t("/api/v1/research/runs", self.headers)
        self.assertEqual(result["status"], "verified_source")
        self.assertEqual(opened[0][:3], ("https://research.internal.example/api/v1/research/runs", "GET", 5.0))
        self.assertNotIn("Cookie", opened[0][3])

    def test_redirect_rejected(self):
        handler = next(h for h in self.t._opener.handlers if h.__class__.__name__ == "_RejectRedirects")
        with self.assertRaises(RuntimeError):
            handler.redirect_request(None, None, 302, "redirect", {}, "https://evil.example")

    def test_oversize_and_bad_json_rejected(self):
        self.t._opener.open = lambda *a, **k: FakeResponse(b"x" * (1024 * 1024 + 1))
        with self.assertRaises(RuntimeError):
            self.t("/api/v1/research/runs", self.headers)
        self.t._opener.open = lambda *a, **k: FakeResponse(b"not-json")
        with self.assertRaises(RuntimeError):
            self.t("/api/v1/research/runs", self.headers)


if __name__ == "__main__":
    unittest.main()
