import unittest
from alpha_lab.research.oidc_browser_wsgi import _validated_origin, _RejectRedirect


class OIDCTransportHardeningTests(unittest.TestCase):
    def test_callback_origin_validation(self):
        self.assertEqual(_validated_origin("https://staging.example/auth/callback"), "https://staging.example")
        for url in (
            "http://staging.example/auth/callback",
            "https://user:pass@staging.example/auth/callback",
            "https://staging.example:444/auth/callback",
            "https://staging.example/auth/callback?token=leak",
            "https://staging.example/auth/callback#fragment",
            "https:///auth/callback",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                _validated_origin(url)

    def test_token_endpoint_redirect_fails_closed(self):
        handler = _RejectRedirect()
        with self.assertRaises(PermissionError):
            handler.redirect_request(None, None, 302, "Found", {},
                                     "https://attacker.example/collect")


if __name__ == "__main__":
    unittest.main()
