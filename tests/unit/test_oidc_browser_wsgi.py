import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse

CRYPTO = importlib.util.find_spec("cryptography") is not None
if CRYPTO:
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes
    from alpha_lab.research.auth0_jwt import Auth0JWTVerifier
    from alpha_lab.research.oidc_browser_wsgi import OIDCBrowserWSGI
    from alpha_lab.research.oidc_durable_store import DurableOIDCStore
    import base64


@unittest.skipUnless(CRYPTO, "Run browser integration tests in dependency-enabled Auth0 CI")
class BrowserOIDCTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = DurableOIDCStore(self.tmp.name + "/auth.sqlite", now=lambda: 2000000000)
        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub = self.private.public_key().public_numbers()
        def b64(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
        jwks = {"keys": [{"kid": "k1", "kty": "RSA", "n": b64(pub.n.to_bytes(256, "big")),
                          "e": b64(pub.e.to_bytes(3, "big"))}]}
        self.issuer = "https://tenant.example.auth0.com/"
        self.verifier = Auth0JWTVerifier(issuer=self.issuer, audience="client-id", jwks=jwks)
        self.claim_nonce = None
        def exchange(code, verifier):
            claims = {"iss": self.issuer, "aud": "client-id", "sub": "auth0|owner",
                      "exp": 2000000200, "iat": 1999999900, "nonce": self.claim_nonce}
            header = b64(json.dumps({"alg": "RS256", "kid": "k1"}).encode())
            payload = b64(json.dumps(claims).encode())
            sig = b64(self.private.sign((header + "." + payload).encode(),
                                        padding.PKCS1v15(), hashes.SHA256()))
            return {"id_token": header + "." + payload + "." + sig}
        self.app = OIDCBrowserWSGI(issuer=self.issuer, client_id="client-id",
            client_secret="test-only-not-real", redirect_uri="https://staging.example/auth/callback",
            store=self.store, verifier=self.verifier, exchange=exchange,
            now=datetime.fromtimestamp(2000000000, timezone.utc))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def request(self, path, method="GET", cookie="", query="", origin=""):
        result = {}
        env = {"PATH_INFO": path, "REQUEST_METHOD": method, "HTTP_COOKIE": cookie,
               "QUERY_STRING": query, "HTTP_ORIGIN": origin}
        def start(status, headers):
            result["status"], result["headers"] = status, dict(headers)
        result["body"] = b"".join(self.app(env, start))
        return result

    def test_login_callback_session_logout_and_replay(self):
        login = self.request("/auth/login")
        self.assertTrue(login["status"].startswith("302"))
        self.assertIn("code_challenge_method=S256", login["headers"]["Location"])
        self.assertIn("Secure", login["headers"]["Set-Cookie"])
        cookie = login["headers"]["Set-Cookie"].split(";", 1)[0]
        jar = SimpleCookie(); jar.load(cookie)
        state, nonce = jar["__Host-alpha_oidc"].value.split(".", 1)
        self.claim_nonce = nonce
        callback = self.request("/auth/callback", cookie=cookie, query="code=example&state=" + state)
        self.assertTrue(callback["status"].startswith("303"))
        sid_cookie = callback["headers"]["Set-Cookie"].split(";", 1)[0]
        self.assertTrue(self.request("/auth/me", cookie=sid_cookie)["status"].startswith("200"))
        self.assertTrue(self.request("/auth/callback", cookie=cookie, query="code=example&state=" + state)["status"].startswith("401"))
        self.assertTrue(self.request("/auth/logout", method="POST", cookie=sid_cookie,
                                     origin="https://attacker.example")["status"].startswith("403"))
        self.assertTrue(self.request("/auth/logout", method="POST", cookie=sid_cookie,
                                     origin="https://staging.example")["status"].startswith("204"))
        self.assertTrue(self.request("/auth/me", cookie=sid_cookie)["status"].startswith("401"))

    def test_nonce_and_state_forgery_rejected(self):
        login = self.request("/auth/login")
        cookie = login["headers"]["Set-Cookie"].split(";", 1)[0]
        jar = SimpleCookie(); jar.load(cookie)
        state, nonce = jar["__Host-alpha_oidc"].value.split(".", 1)
        self.claim_nonce = "wrong"
        self.assertTrue(self.request("/auth/callback", cookie=cookie,
                                     query="code=example&state=" + state)["status"].startswith("401"))
        self.assertTrue(self.request("/auth/callback", cookie=cookie,
                                     query="code=example&state=forged")["status"].startswith("401"))
        self.assertTrue(self.request("/api/trade", method="POST")["status"].startswith("404"))

if __name__ == "__main__":
    unittest.main()
