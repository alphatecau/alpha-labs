import base64
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import importlib.util
CRYPTO_AVAILABLE = importlib.util.find_spec('cryptography') is not None
if CRYPTO_AVAILABLE:
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes
    from alpha_lab.research.auth0_jwt import Auth0JWTVerifier
    from alpha_lab.research.auth0_staging_app import build_auth0_app


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def jwt(private, claims, header=None):
    h = b64(json.dumps(header or {"alg": "RS256", "kid": "test", "typ": "JWT"}).encode())
    p = b64(json.dumps(claims).encode())
    sig = private.sign((h + "." + p).encode(), padding.PKCS1v15(), hashes.SHA256())
    return h + "." + p + "." + b64(sig)


@unittest.skipUnless(CRYPTO_AVAILABLE, 'Auth0 security tests run in dedicated cryptography-enabled CI job')
class Auth0StagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub = cls.private.public_key().public_numbers()
        cls.jwks = {"keys": [{"kid": "test", "kty": "RSA", "alg": "RS256",
                              "n": b64(pub.n.to_bytes((pub.n.bit_length()+7)//8, "big")),
                              "e": b64(pub.e.to_bytes(3, "big"))}]}
        cls.issuer = "https://alpha-labs-dev.example.auth0.com/"
        cls.audience = "https://alpha-labs-staging-api"
        cls.now = datetime.fromtimestamp(2000000000, tz=timezone.utc)

    def claims(self, sub="auth0|owner"):
        return {"iss": self.issuer, "aud": self.audience, "sub": sub,
                "iat": 1999999900, "exp": 2000000100}

    def verifier(self):
        return Auth0JWTVerifier(issuer=self.issuer, audience=self.audience, jwks=self.jwks)

    def test_valid_owner_and_distinct_nonowner(self):
        v = self.verifier()
        a = v.verify(jwt(self.private, self.claims()), now=self.now)
        b = v.verify(jwt(self.private, self.claims("auth0|other")), now=self.now)
        self.assertNotEqual(a.subject, b.subject)
        self.assertEqual(a, v.verify(jwt(self.private, self.claims()), now=self.now))

    def test_adversarial_tokens_fail_closed(self):
        v = self.verifier()
        bad = [
            dict(iss="https://wrong.example/"), dict(aud="wrong"),
            dict(exp=1999999999), dict(iat=2000000200), dict(nbf=2000000001),
            dict(sub=""), dict(sub="bad\nsubject"),
        ]
        for override in bad:
            with self.subTest(override=override), self.assertRaises(PermissionError):
                v.verify(jwt(self.private, {**self.claims(), **override}), now=self.now)
        for header in [{"alg": "none", "kid": "test"}, {"alg": "HS256", "kid": "test"},
                       {"alg": "RS256", "kid": "unknown"}, {"alg": "RS256", "kid": "test", "jku": "https://evil.example"}]:
            with self.subTest(header=header), self.assertRaises(PermissionError):
                v.verify(jwt(self.private, self.claims(), header), now=self.now)
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with self.assertRaises(PermissionError):
            v.verify(jwt(other, self.claims()), now=self.now)
        with self.assertRaises(PermissionError):
            v.verify("a.b", now=self.now)

    def test_staging_owner_only_and_no_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {"ALPHA_AUTH0_ISSUER": self.issuer, "ALPHA_AUTH0_AUDIENCE": self.audience,
                      "ALPHA_AUTH0_JWKS_JSON": json.dumps(self.jwks),
                      "ALPHA_AUTH0_OWNER_SUBJECT": "auth0|owner", "ALPHA_PAPER_DATA_DIR": directory}
            app = build_auth0_app(config)
            app.now = lambda: self.now

            def request(token=None, method="GET", path="/api/research/paper/status"):
                result = {}
                environ = {"PATH_INFO": path, "REQUEST_METHOD": method, "QUERY_STRING": ""}
                if token is not None:
                    environ["HTTP_AUTHORIZATION"] = "Bearer " + token
                def start(status, headers):
                    result["status"] = status
                result["body"] = b"".join(app(environ, start))
                return result

            self.assertTrue(request(jwt(self.private, self.claims()))["status"].startswith("200"))
            self.assertTrue(request(jwt(self.private, self.claims("auth0|other")))["status"].startswith("404"))
            self.assertTrue(request()["status"].startswith("401"))
            self.assertTrue(request("forged")["status"].startswith("401"))
            self.assertTrue(request(jwt(self.private, self.claims()), method="POST")["status"].startswith("405"))
            self.assertTrue(request(jwt(self.private, self.claims()), path="/api/trade")["status"].startswith("404"))
            app.accounts.close()
            config["ALPHA_AUTH0_JWKS_JSON"] = "{}"
            with self.assertRaises(RuntimeError):
                build_auth0_app(config)

if __name__ == "__main__":
    unittest.main()
