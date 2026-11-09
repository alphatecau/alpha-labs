import unittest
from alpha_lab.research.trusted_proxy_boundary import canonicalise_proxy_environ, canonicalise_verified_peer


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

    def test_peer_address_must_be_in_explicit_trusted_network(self):
        env = {**self.env, "REMOTE_ADDR": "10.12.0.4"}
        result = canonicalise_verified_peer(
            env, trusted_peer_cidrs=["10.12.0.0/24"], expected_origin=self.origin)
        self.assertEqual(result["wsgi.url_scheme"], "https")
        for remote in ("10.13.0.4", "203.0.113.1", "not-an-ip"):
            with self.subTest(remote=remote), self.assertRaises(PermissionError):
                canonicalise_verified_peer(
                    {**env, "REMOTE_ADDR": remote},
                    trusted_peer_cidrs=["10.12.0.0/24"], expected_origin=self.origin)
        with self.assertRaises(ValueError):
            canonicalise_verified_peer(env, trusted_peer_cidrs=[], expected_origin=self.origin)
        with self.assertRaises(PermissionError):
            canonicalise_verified_peer(
                {**env, "HTTP_X_FORWARDED_PROTO": "https"},
                trusted_peer_cidrs=["10.12.0.0/24"], expected_origin=self.origin)

    def test_host_mismatch_and_bad_origin_fail_closed(self):
        with self.assertRaises(PermissionError):
            canonicalise_proxy_environ({**self.env, "HTTP_HOST": "attacker.example"}, trusted_peer=True, expected_origin=self.origin)
        with self.assertRaises(ValueError):
            canonicalise_proxy_environ(self.env, trusted_peer=True, expected_origin="http://staging.example.com")


if __name__ == "__main__":
    unittest.main()
