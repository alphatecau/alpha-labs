import importlib.util
import unittest

CRYPTO = importlib.util.find_spec("cryptography") is not None
if CRYPTO:
    from test_oidc_browser_wsgi import BrowserOIDCTests
else:
    BrowserOIDCTests = unittest.TestCase


@unittest.skipUnless(CRYPTO, "Requires crypto-enabled CI")
class ProxyHostSecurityTests(BrowserOIDCTests):
    def test_reject_host_spoofing_and_forwarded_headers(self):
        def call(changes):
            env = {"PATH_INFO": "/auth/login", "REQUEST_METHOD": "GET",
                   "QUERY_STRING": "", "wsgi.url_scheme": "https",
                   "HTTP_HOST": "staging.example"}
            env.update(changes)
            out = {}
            def start(status, headers):
                out["status"] = status
            list(self.app(env, start))
            return out["status"]
        self.assertTrue(call({}).startswith("302"))
        for changes in (
            {"HTTP_HOST": "evil.example"},
            {"HTTP_HOST": "staging.example.evil.example"},
            {"HTTP_X_FORWARDED_HOST": "staging.example"},
            {"HTTP_X_FORWARDED_PROTO": "https"},
            {"HTTP_FORWARDED": "host=staging.example"},
            {"wsgi.url_scheme": "http"},
        ):
            with self.subTest(changes=changes):
                self.assertTrue(call(changes).startswith("403"))


if __name__ == "__main__":
    unittest.main()
