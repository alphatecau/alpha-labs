"""Exercise real urllib redirect processing using a synthetic protocol handler."""
import io
import json
import unittest
import urllib.request
import urllib.response
from email.message import Message
from unittest.mock import patch

from alpha_lab.data import public_https
from alpha_lab.data.adapters import binance_archive, kraken_ohlc
from deployment.staging_probe import main as probe_main


class PublicTransportTests(unittest.TestCase):
    def transport(self, *, location=None, payload=b'{"synthetic":true}', status=200, final_url=None):
        seen = []

        class SyntheticHTTP(urllib.request.BaseHandler):
            handler_order = 0

            def https_open(self, request):
                seen.append(request)
                headers = Message()
                if location:
                    headers["Location"] = location
                response = urllib.response.addinfourl(io.BytesIO(payload), headers,
                    final_url or request.full_url, 302 if location else status)
                response.msg = "Synthetic"
                return response

            def http_open(self, request):
                raise AssertionError("redirect target must never be fetched")

        original = urllib.request.build_opener
        return seen, lambda *handlers: original(SyntheticHTTP(), *handlers)

    def test_actual_redirect_processing_is_rejected_for_both_downloaders(self):
        for target in ("http://127.0.0.1:9/synthetic", "https://unexpected.example/data"):
            for call in (lambda: binance_archive._read_url(binance_archive.BASE + "/synthetic.zip"),
                         lambda: kraken_ohlc.fetch_public_ohlc()):
                seen, factory = self.transport(location=target)
                with patch.object(public_https, "build_opener", side_effect=factory):
                    with self.assertRaisesRegex(ValueError, "redirect refused"):
                        call()
                self.assertEqual(len(seen), 1)
                self.assertEqual(seen[0].get_method(), "GET")
                self.assertIsNone(seen[0].get_header("Authorization"))

    def test_size_status_origin_and_timeout_fail_closed(self):
        for options in ({"payload": b"01234567890"}, {"status": 206},
                        {"final_url": "https://other.example/"}):
            _, factory = self.transport(**options)
            with patch.object(public_https, "build_opener", side_effect=factory), self.assertRaises(ValueError):
                public_https.read_public_https("https://trusted.example/data", origin="https://trusted.example", max_bytes=10, timeout=1)
        for url in ("file:///tmp/synthetic", "http://trusted.example/data", "https://user@trusted.example/data"):
            with patch.object(public_https, "build_opener") as opened, self.assertRaises(ValueError):
                public_https.read_public_https(url, origin="https://trusted.example", max_bytes=10, timeout=1)
            opened.assert_not_called()
        for timeout in (float("inf"), 0, -1, True, 36):
            with self.assertRaises(ValueError):
                public_https.read_public_https("https://trusted.example/data", origin="https://trusted.example", max_bytes=10, timeout=timeout)

    def test_kraken_rejects_a_valid_json_prefix_of_an_oversized_body(self):
        _, factory = self.transport(payload=b"{}" + b" " * 3_000_000)
        with patch.object(public_https, "build_opener", side_effect=factory), self.assertRaisesRegex(ValueError, "exceeds limit"):
            kraken_ohlc.fetch_public_ohlc()

    def test_valid_payload_and_hash_are_preserved(self):
        body = b'{"synthetic":true}'
        _, factory = self.transport(payload=body)
        with patch.object(public_https, "build_opener", side_effect=factory):
            payload, digest = kraken_ohlc.fetch_public_ohlc()
        self.assertEqual(payload, json.loads(body))
        import hashlib
        self.assertEqual(digest, hashlib.sha256(body).hexdigest())

    def test_probe_diagnostic_main_binds_only_loopback(self):
        with patch("wsgiref.simple_server.make_server") as server, patch.dict("os.environ", {"PORT": "10000"}):
            probe_main()
        self.assertEqual(server.call_args.args[:2], ("127.0.0.1", 10000))
