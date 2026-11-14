"""Adversarial Auth0 issuer and redirect origin validation."""
import unittest

from deployment.auth0_pkce_callback import Auth0PKCEFlow


class Auth0URLHardeningTests(unittest.TestCase):
    def test_issuer_userinfo_and_ports_rejected(self):
        for issuer in ("https://user@auth.example/", "https://auth.example:444/",
                       "https://user:pass@auth.example/"):
            with self.subTest(issuer=issuer), self.assertRaises(ValueError):
                Auth0PKCEFlow(issuer=issuer, client_id="test",
                              redirect_uri="https://isolated.example/auth/callback",
                              state_store=object())

    def test_redirect_userinfo_and_ports_rejected(self):
        for redirect in ("https://user@isolated.example/auth/callback",
                         "https://isolated.example:444/auth/callback"):
            with self.subTest(redirect=redirect), self.assertRaises(ValueError):
                Auth0PKCEFlow(issuer="https://auth.example/", client_id="test",
                              redirect_uri=redirect, state_store=object())


if __name__ == "__main__":
    unittest.main()
