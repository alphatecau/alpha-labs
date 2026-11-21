"""No-network tests for the non-authorising remote readiness observer."""
import io
import json
import unittest
from unittest.mock import patch

from tools.level3_staging.remote_readiness import RemoteNotReady, observe_readiness


class FakeResponse:
    status = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, data, status=200, content_type="application/json"):
        self.body = io.BytesIO(data)
        self.status = status
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.body.read(size)


class RemoteReadinessTests(unittest.TestCase):
    def test_rejects_insecure_or_ambiguous_origins(self):
        for origin in ("http://broker.example", "https://user:pass@broker.example",
                       "https://broker.example/path", "https://broker.example/?x=1",
                       "https://broker.example/#fragment", "", None):
            with self.subTest(origin=origin), self.assertRaises(RemoteNotReady):
                observe_readiness(origin, opener=lambda *a, **k: self.fail("network called"))

    def test_denied_or_missing_readiness(self):
        for response in (
            FakeResponse(b'{"ready":false}'),
            FakeResponse(b'{"alive":true}'),
            FakeResponse(b'{"ready":"true"}'),
            FakeResponse(b'{"ready":true}', status=503),
            FakeResponse(b'{"ready":true}', content_type="text/html"),
            FakeResponse(b'not-json'),
            FakeResponse(b'x' * 4097),
        ):
            with self.subTest(body=response.body.getvalue()[:30]), self.assertRaises(RemoteNotReady):
                observe_readiness("https://broker.example", opener=lambda *a, r=response, **k: r)

    def test_reported_ready_never_authorises_writes(self):
        result = observe_readiness(
            "https://broker.example",
            opener=lambda *a, **k: FakeResponse(json.dumps({"ready": True}).encode()),
        )
        self.assertEqual(result, {"reachable": True, "reported_ready": True, "authorised": False})

    def test_transport_error_fails_closed(self):
        with self.assertRaises(RemoteNotReady):
            observe_readiness("https://broker.example", opener=lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))


if __name__ == "__main__":
    unittest.main()
