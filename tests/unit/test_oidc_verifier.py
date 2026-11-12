import base64
import json
import unittest
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from deployment.oidc_verifier import OIDCVerifier


def b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


class OIDCTests(unittest.TestCase):
    def setUp(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        p = self.key.public_key().public_numbers()
        self.jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "key1",
                    "alg": "RS256",
                    "n": b64(p.n.to_bytes(256, "big")),
                    "e": b64(p.e.to_bytes(3, "big")),
                }
            ]
        }
        self.verifier = OIDCVerifier(
            issuer="https://issuer.example",
            audience="alpha-client",
            jwks=self.jwks,
            clock=lambda: 1000,
        )

    def token(self, **overrides):
        claims = {
            "iss": "https://issuer.example",
            "aud": "alpha-client",
            "sub": "user-a",
            "iat": 990,
            "exp": 1100,
        }
        claims.update(overrides)
        head = b64(json.dumps({"alg": "RS256", "kid": "key1"}).encode())
        body = b64(json.dumps(claims).encode())
        data = (head + "." + body).encode()
        return (
            head
            + "."
            + body
            + "."
            + b64(self.key.sign(data, padding.PKCS1v15(), hashes.SHA256()))
        )

    def test_valid_owner(self):
        a = self.verifier(self.token())["owner_id"]
        b = self.verifier(self.token(sub="user-b"))["owner_id"]
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith("oidc_"))

    def test_bad_audience(self):
        with self.assertRaises(PermissionError):
            self.verifier(self.token(aud="other"))

    def test_bad_issuer(self):
        with self.assertRaises(PermissionError):
            self.verifier(self.token(iss="https://other.example"))

    def test_expired(self):
        with self.assertRaises(PermissionError):
            self.verifier(self.token(exp=999))

    def test_future_issued(self):
        with self.assertRaises(PermissionError):
            self.verifier(self.token(iat=1100))

    def test_tampered_signature(self):
        tok = self.token(sub="user-a")
        head, body, sig = tok.split(".")
        with self.assertRaises(PermissionError):
            self.verifier(
                head + "." + b64(json.dumps({"sub": "user-b"}).encode()) + "." + sig
            )

    def test_reject_wrong_azp_even_with_single_audience(self):
        with self.assertRaises(PermissionError):
            self.verifier(self.token(azp="other-client"))

    def test_reject_malformed_issuer_configuration(self):
        for issuer in (
            "https://issuer.example@evil.example",
            "https://issuer.example/path",
            "https://issuer.example?x=1",
        ):
            with self.assertRaises(ValueError):
                OIDCVerifier(issuer=issuer, audience="alpha-client", jwks=self.jwks)

    def test_reject_duplicate_claim_members(self):
        head = b64(json.dumps({"alg": "RS256", "kid": "key1"}).encode())
        body = b64(
            b'{"iss":"https://issuer.example","aud":"alpha-client","sub":"user-a","sub":"user-b","iat":990,"exp":1100}'
        )
        data = (head + "." + body).encode()
        token = (
            head
            + "."
            + body
            + "."
            + b64(self.key.sign(data, padding.PKCS1v15(), hashes.SHA256()))
        )
        with self.assertRaises(PermissionError):
            self.verifier(token)

    def test_missing_key(self):
        verifier = OIDCVerifier(
            issuer="https://issuer.example",
            audience="alpha-client",
            jwks={"keys": []},
            clock=lambda: 1000,
        )
        with self.assertRaises(PermissionError):
            verifier(self.token())

    def test_reject_unsigned(self):
        with self.assertRaises(PermissionError):
            self.verifier("eyJhbGciOiJub25lIn0.e30.")


if __name__ == "__main__":
    unittest.main()
