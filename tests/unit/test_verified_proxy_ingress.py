import unittest
from deployment.verified_proxy_ingress import VerifiedProxyIngress


class VerifiedProxyTests(unittest.TestCase):
    def setUp(self):
        self.seen = []
        def app(env, start):
            self.seen.append(env)
            start("200 OK", [])
            return [b"ok"]
        self.proxy = VerifiedProxyIngress(
            app, "https://alpha.example", trusted_peer_cidrs=["10.77.0.0/24"])

    def call(self, **extra):
        env = {"REMOTE_ADDR": "10.77.0.2", "HTTP_HOST": "alpha.example",
               "HTTP_X_FORWARDED_PROTO": "https", "wsgi.url_scheme": "http"}
        env.update(extra)
        status = []
        self.proxy(env, lambda s, h: status.append(s))
        return status[0]

    def test_accepts_trusted_peer_and_strips_headers(self):
        self.assertEqual(self.call(), "200 OK")
        self.assertEqual(self.seen[0]["wsgi.url_scheme"], "https")
        self.assertNotIn("HTTP_X_FORWARDED_PROTO", self.seen[0])

    def test_rejects_untrusted_peer_and_missing_peer(self):
        self.assertEqual(self.call(REMOTE_ADDR="203.0.113.1"), "403 Forbidden")
        self.assertEqual(self.call(REMOTE_ADDR="invalid"), "403 Forbidden")

    def test_rejects_spoofed_or_ambiguous_forwarding(self):
        for field, value in (("HTTP_X_FORWARDED_FOR", "127.0.0.1"),
                             ("HTTP_FORWARDED", "proto=https"),
                             ("HTTP_X_FORWARDED_HOST", "alpha.example"),
                             ("HTTP_X_REAL_IP", "127.0.0.1"),
                             ("HTTP_X_FORWARDED_PORT", "443"),
                             ("HTTP_X_FORWARDED_PROTO", "http"),
                             ("HTTP_X_FORWARDED_PROTO", "https,http"),
                             ("HTTP_HOST", "evil.example")):
            self.assertEqual(self.call(**{field: value}), "403 Forbidden")
        self.assertEqual(len(self.seen), 0)

    def test_refuses_unrestricted_trust(self):
        with self.assertRaises(ValueError):
            VerifiedProxyIngress(lambda e, s: [], "https://alpha.example",
                                 trusted_peer_cidrs=["0.0.0.0/0"])


if __name__ == "__main__":
    unittest.main()
