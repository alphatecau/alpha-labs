"""No-network EODHD transport security tests."""
import io
import os
from unittest.mock import patch
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request

from alpha_lab.data.eodhd_transport import TransportError, https_transport, MAX_RESPONSE_BYTES

PARAMS = {"api_token": "DO_NOT_LOG_THIS_TOKEN", "from": "2025-01-01",
          "to": "2025-01-31", "fmt": "json"}


class FakeResponse:
    status = 200
    def __init__(self, body=b"[]", status=200):
        self.stream = io.BytesIO(body)
        self.status = status
    def read(self, limit):
        return self.stream.read(limit)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response, self.error = response or FakeResponse(), error
        self.requests = []
    def open(self, req, timeout):
        self.requests.append((req, timeout))
        if self.error:
            raise self.error
        return self.response


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.network_gate = patch.dict(os.environ, {"ALPHA_EODHD_NETWORK_ENABLED": "true"})
        self.network_gate.start()
        self.addCleanup(self.network_gate.stop)

    def test_network_disabled_by_default(self):
        fake = FakeOpener()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(TransportError):
                https_transport("/api/eod/SPY.US", PARAMS, opener=fake)
        self.assertEqual(fake.requests, [])

    def test_fixed_host_https_and_timeout(self):
        fake = FakeOpener()
        result = https_transport("/api/eod/SPY.US", PARAMS, opener=fake)
        req, timeout = fake.requests[0]
        self.assertEqual(req.full_url.split("?")[0], "https://eodhd.com/api/eod/SPY.US")
        self.assertEqual(timeout, 8)
        self.assertEqual(result.body, "[]")

    def test_rejects_path_injection_without_request(self):
        fake = FakeOpener()
        for path in ("/api/eod/../secrets", "/api/eod/X?evil=1",
                     "https://attacker.test/api/eod/SPY", "/api/eod/"):
            with self.subTest(path=path), self.assertRaises(TransportError):
                https_transport(path, PARAMS, opener=fake)
        self.assertEqual(fake.requests, [])

    def test_rejects_excess_body_and_bad_encoding(self):
        for body in (b"x" * (MAX_RESPONSE_BYTES + 1), b"\xff"):
            with self.assertRaises(TransportError):
                https_transport("/api/eod/SPY.US", PARAMS,
                                opener=FakeOpener(FakeResponse(body)))

    def test_errors_do_not_expose_token(self):
        for error in (URLError("DO_NOT_LOG_THIS_TOKEN"), TimeoutError("DO_NOT_LOG_THIS_TOKEN")):
            with self.assertRaises(TransportError) as ctx:
                https_transport("/api/eod/SPY.US", PARAMS, opener=FakeOpener(error=error))
            self.assertNotIn(PARAMS["api_token"], str(ctx.exception))

    def test_invalid_dates_fail_before_transport(self):
        fake = FakeOpener()
        for overrides in ({"from": "invalid"}, {"from": "2025-02-01", "to": "2025-01-01"}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(TransportError):
                    https_transport("/api/eod/SPY.US", {**PARAMS, **overrides}, opener=fake)
        self.assertEqual(fake.requests, [])

    def test_redirect_target_drift_is_rejected(self):
        class RedirectedResponse(FakeResponse):
            def geturl(self):
                return "https://attacker.example/steal"
        with self.assertRaises(TransportError):
            https_transport("/api/eod/SPY.US", PARAMS,
                            opener=FakeOpener(RedirectedResponse()))

    def test_http_errors_redacted(self):
        error = HTTPError("https://eodhd.com/?api_token=DO_NOT_LOG_THIS_TOKEN", 429,
                          "secret", {}, None)
        reply = https_transport("/api/eod/SPY.US", PARAMS, opener=FakeOpener(error=error))
        self.assertEqual(reply.status, 429)
        self.assertEqual(reply.body, "")


if __name__ == "__main__":
    unittest.main()
