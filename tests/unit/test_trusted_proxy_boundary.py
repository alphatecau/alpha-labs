import unittest
from alpha_lab.research.trusted_proxy_boundary import canonicalise_proxy_environ


class TrustedProxyBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.origin = "https://staging.example.com"
        self.env = {"HTTP_HOST": "staging.example.com", "wsgi.url_scheme": "http"}

    def test_only_explicitly_trusted_peer_is_canonicalised(self):
        with self.assertRaises(PermissionError):
            canonicalise_proxy_environ(self.env, trusted_peer=False, expected_origin=self.origin)
        result = canonicalise_proxy_environ(self.env, trusted_peer=True, expected_origin=self.origin)
        self.assertEqual(result["wsgi.url_scheme"], "https")
        self.assertEqual(self.env["wsgi.url_scheme"], "http")

    def test_spoofed_forwarded_metadata_rejected(self):
        for key in ("HTTP_X_FORWARDED_PROTO", "HTTP_X_FORWARDED_HOST", "HTTP_FORWARDED"):
            with self.subTest(key=key):
                with self.assertRaises(PermissionError):
                    canonicalise_proxy_environ({**self.env, key: "https"}, trusted_peer=True, expected_origin=self.origin)

    def test_host_mismatch_and_bad_origin_fail_closed(self):
        with self.assertRaises(PermissionError):
            canonicalise_proxy_environ({**self.env, "HTTP_HOST": "attacker.example"}, trusted_peer=True, expected_origin=self.origin)
        with self.assertRaises(ValueError):
            canonicalise_proxy_environ(self.env, trusted_peer=True, expected_origin="http://staging.example.com")


if __name__ == "__main__":
    unittest.main()
