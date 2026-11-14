"""Positive and adversarial RS256 Auth0 ID-token verification tests."""
import base64
import json
import unittest

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from deployment.auth0_verified_identity import Auth0IDTokenVerifier


def enc(value):
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def enc_bytes(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


class SignedAuth0TokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        numbers = cls.key.public_key().public_numbers()
        cls.jwks = {"keys": [{
            "kid": "test-key", "kty": "RSA", "use": "sig", "alg": "RS256",
            "n": enc_bytes(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
            "e": enc_bytes(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
        }]}

    def setUp(self):
        self.issuer = "https://alpha-labs-dev.au.auth0.com/"
        self.client_id = "test-client-id"
        self.nonce = "server-generated-nonce-123456"
        self.verifier = Auth0IDTokenVerifier(
            issuer=self.issuer, client_id=self.client_id,
            jwks=self.jwks, clock=lambda: 1800000000)
        self.claims = {
            "iss": self.issuer, "aud": self.client_id,
            "sub": "auth0|alice", "nonce": self.nonce,
            "iat": 1799999990, "exp": 1800000300,
        }

    def token(self, claims=None):
        payload = self.claims if claims is None else claims
        signing_input = enc({"alg": "RS256", "typ": "JWT", "kid": "test-key"}) + "." + enc(payload)
        signature = self.key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
        return signing_input + "." + enc_bytes(signature)

    def test_signed_token_accepted(self):
        principal = self.verifier.verify(self.token(), expected_nonce=self.nonce)
        self.assertEqual(principal.subject, "auth0|alice")
        self.assertEqual(principal.issuer, self.issuer)

    def test_modified_payload_rejected(self):
        token = self.token()
        segments = token.split(".")
        forged = dict(self.claims, sub="auth0|bob")
        segments[1] = enc(forged)
        with self.assertRaises(PermissionError):
            self.verifier.verify(".".join(segments), expected_nonce=self.nonce)

    def test_wrong_nonce_rejected(self):
        with self.assertRaises(PermissionError):
            self.verifier.verify(self.token(), expected_nonce="different-nonce-123456789")

    def test_wrong_audience_rejected(self):
        with self.assertRaises(PermissionError):
            self.verifier.verify(self.token(dict(self.claims, aud="other-client")), expected_nonce=self.nonce)

    def test_expired_token_rejected(self):
        with self.assertRaises(PermissionError):
            self.verifier.verify(self.token(dict(self.claims, exp=1799999999)), expected_nonce=self.nonce)

    def test_wrong_issuer_rejected(self):
        with self.assertRaises(PermissionError):
            self.verifier.verify(self.token(dict(self.claims, iss="https://other.example/")), expected_nonce=self.nonce)


if __name__ == "__main__":
    unittest.main()
