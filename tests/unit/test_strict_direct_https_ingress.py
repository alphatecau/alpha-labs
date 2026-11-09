import unittest
from deployment.strict_direct_https_ingress import StrictDirectHTTPSIngress


class StrictIngressTests(unittest.TestCase):
    def setUp(self):
        self.called = 0
        def app(env, start):
            self.called += 1
            start("200 OK", [])
            return [b"ok"]
        self.ingress = StrictDirectHTTPSIngress(app, "https://alpha.example")

    def invoke(self, **overrides):
        env = {"wsgi.url_scheme": "https", "HTTP_HOST": "alpha.example"}
        env.update(overrides)
        statuses = []
        body = b"".join(self.ingress(env, lambda status, headers: statuses.append(status)))
        return statuses[0], body

    def test_accepts_exact_direct_https(self):
        self.assertEqual(self.invoke()[0], "200 OK")
        self.assertEqual(self.called, 1)

    def test_rejects_http_and_host_mismatch(self):
        for override in ({"wsgi.url_scheme": "http"},
                         {"HTTP_HOST": "evil.example"},
                         {"HTTP_HOST": "alpha.example:444"}):
            self.assertEqual(self.invoke(**override)[0], "403 Forbidden")
        self.assertEqual(self.called, 0)

    def test_rejects_forwarded_metadata_even_when_https(self):
        for name in ("HTTP_FORWARDED", "HTTP_X_FORWARDED_PROTO",
                     "HTTP_X_FORWARDED_HOST", "HTTP_X_FORWARDED_FOR",
                     "HTTP_X_REAL_IP", "HTTP_X_FORWARDED_PORT"):
            self.assertEqual(self.invoke(**{name: "https"})[0], "403 Forbidden")
        self.assertEqual(self.called, 0)

    def test_invalid_origin_rejected(self):
        for origin in ("http://alpha.example", "https://alpha.example/path",
                       "https://user@alpha.example"):
            with self.assertRaises(ValueError):
                StrictDirectHTTPSIngress(lambda e, s: [], origin)


if __name__ == "__main__":
    unittest.main()
