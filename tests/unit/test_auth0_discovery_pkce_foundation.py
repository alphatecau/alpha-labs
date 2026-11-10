import hashlib
import unittest
from urllib.parse import urlsplit, parse_qs
from deployment.auth0_login_flow import Auth0LoginFlow
from deployment.auth0_trusted_jwks import load_auth0_verifier

class MemoryState:
    def __init__(self): self.records = {}
    def put(self, digest, record, ttl): self.records[digest] = dict(record)
    def consume(self, digest): return self.records.pop(digest, None)

class Auth0FoundationTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryState()
        self.flow = Auth0LoginFlow(issuer="https://tenant.example.auth0.com", client_id="client-id",
            redirect_uri="https://bff.example/auth/callback", state_store=self.store, clock=lambda: 1000)

    def test_pkce_s256_and_one_use_nonce(self):
        url = self.flow.begin()
        p = parse_qs(urlsplit(url).query)
        self.assertEqual(p["code_challenge_method"], ["S256"])
        self.assertEqual(p["response_type"], ["code"])
        state = p["state"][0]
        record = self.store.records[hashlib.sha256(state.encode()).hexdigest()]
        import base64
        challenge = base64.urlsafe_b64encode(hashlib.sha256(record["verifier"].encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(p["code_challenge"], [challenge])
        claims = {"verified": True, "nonce": record["nonce"], "owner_id": "test-owner"}
        result = self.flow.validate_callback(state=state, code="synthetic-code", id_token="synthetic-token",
            verifier=lambda token: claims)
        self.assertEqual(result["pkce_verifier"], record["verifier"])
        with self.assertRaises(PermissionError):
            self.flow.validate_callback(state=state, code="synthetic-code", id_token="synthetic-token",
                verifier=lambda token: claims)

    def test_wrong_nonce_fails_closed_and_consumes_state(self):
        state = parse_qs(urlsplit(self.flow.begin()).query)["state"][0]
        with self.assertRaises(PermissionError):
            self.flow.validate_callback(state=state, code="code", id_token="token",
                verifier=lambda token: {"verified": True, "nonce": "incorrect"})
        self.assertFalse(self.store.records)

    def test_reject_userinfo_in_config(self):
        for issuer, callback in (
            ("https://tenant.example.auth0.com@evil.example", "https://bff.example/auth/callback"),
            ("https://tenant.example.auth0.com", "https://bff.example@evil.example/auth/callback"),
            ("https://tenant.example.auth0.com", "https://bff.example/auth/callback?redirect=evil")):
            with self.assertRaises(ValueError):
                Auth0LoginFlow(issuer=issuer, client_id="client", redirect_uri=callback,
                    state_store=self.store)

    def test_pinned_discovery_and_jwks(self):
        issuer = "https://tenant.example.auth0.com"
        calls = []
        def fetch(url):
            calls.append(url)
            if url.endswith("openid-configuration"):
                return {"issuer": issuer+"/", "jwks_uri": issuer+"/.well-known/jwks.json"}
            return {"keys": [{"kid": "synthetic", "kty": "RSA"}]}
        verifier = load_auth0_verifier(issuer, "client", fetch=fetch)
        self.assertEqual(verifier.issuer, issuer+"/")
        self.assertEqual(len(calls), 2)

    def test_untrusted_jwks_endpoint_rejected(self):
        issuer = "https://tenant.example.auth0.com"
        with self.assertRaises(PermissionError):
            load_auth0_verifier(issuer, "client", fetch=lambda url: {
                "issuer": issuer+"/", "jwks_uri": "https://evil.example/keys"})
if __name__ == "__main__": unittest.main()
