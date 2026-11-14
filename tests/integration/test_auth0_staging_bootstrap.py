"""Auth0 JWKS trust boundary and isolated composition acceptance tests."""
import unittest
from unittest.mock import patch, MagicMock

from deployment.auth0_jwks import fetch_auth0_jwks
from deployment.auth0_staging_composition import compose_auth0_staging


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return b'{"keys":[{"kty":"RSA","kid":"test"}]}'


class BootstrapTests(unittest.TestCase):
    def test_reject_non_https_and_issuer_path(self):
        for issuer in ("http://example.com/", "https://example.com/evil",
                       "https://example.com/?next=x", "https://user@example.com/"):
            with self.subTest(issuer=issuer), self.assertRaises(ValueError):
                fetch_auth0_jwks(issuer)

    def test_pinned_url_and_bounded_fetch(self):
        with patch("deployment.auth0_jwks.urllib.request.build_opener") as build:
            opener = build.return_value
            opener.open.return_value = FakeResponse()
            result = fetch_auth0_jwks("https://alpha-labs-dev.au.auth0.com/")
            self.assertEqual(len(result["keys"]), 1)
            request = opener.open.call_args.args[0]
            self.assertEqual(request.full_url,
                             "https://alpha-labs-dev.au.auth0.com/.well-known/jwks.json")
            self.assertEqual(opener.open.call_args.kwargs["timeout"], 8)

    def test_composition_requires_restricted_separate_stores(self):
        factory = lambda: None
        with self.assertRaises(ValueError):
            compose_auth0_staging(
                issuer="https://alpha-labs-dev.au.auth0.com/",
                client_id="client", client_secret="not-a-real-secret",
                origin="https://isolated.example", jwks={"keys":[]},
                oauth_connect=factory, session_connect=factory,
                ownership=MagicMock(), reader=MagicMock())

    def test_composition_refuses_missing_ownership_gate(self):
        with self.assertRaises(ValueError):
            compose_auth0_staging(
                issuer="https://alpha-labs-dev.au.auth0.com/",
                client_id="client", client_secret="not-a-real-secret",
                origin="https://isolated.example", jwks={"keys":[]},
                oauth_connect=lambda: None, session_connect=lambda: None,
                ownership=None, reader=MagicMock())


if __name__ == "__main__":
    unittest.main()
