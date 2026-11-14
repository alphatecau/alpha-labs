"""Negative Auth0 verifier tests: forged/unbound tokens must fail."""
import base64
import json
import unittest
from deployment.auth0_verified_identity import Auth0IDTokenVerifier


def enc(value):
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


class Auth0VerifierNegativeTests(unittest.TestCase):
    def setUp(self):
        self.verifier = Auth0IDTokenVerifier(
            issuer="https://alpha-labs-dev.au.auth0.com/",
            client_id="DP8p06i6yDAI5RLR0veQhVL4KXPM58kj",
            jwks={"keys": []},
            clock=lambda: 1800000000,
        )
        self.claims = {
            "iss": "https://alpha-labs-dev.au.auth0.com/",
            "aud": "DP8p06i6yDAI5RLR0veQhVL4KXPM58kj",
            "sub": "auth0|test",
            "nonce": "server-issued-nonce-value",
            "iat": 1799999900,
            "exp": 1800000100,
        }

    def test_missing_nonce_rejected(self):
        with self.assertRaises(PermissionError):
            self.verifier.verify("invalid", expected_nonce="")

    def test_none_algorithm_rejected(self):
        token = enc({"alg": "none", "typ": "JWT"}) + "." + enc(self.claims) + "."
        with self.assertRaises(PermissionError):
            self.verifier.verify(token, expected_nonce=self.claims["nonce"])

    def test_unsigned_rs256_rejected(self):
        token = enc({"alg": "RS256", "kid": "forged"}) + "." + enc(self.claims) + ".AA"
        with self.assertRaises(PermissionError):
            self.verifier.verify(token, expected_nonce=self.claims["nonce"])

    def test_untrusted_issuer_rejected(self):
        with self.assertRaises(ValueError):
            Auth0IDTokenVerifier(issuer="http://untrusted.example", client_id="test", jwks={"keys": []})


if __name__ == "__main__":
    unittest.main()
