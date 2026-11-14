import unittest
from deployment.auth0_trusted_jwks import load_auth0_verifier
from deployment.postgres_pkce_state_store import PostgresPKCEStateStore

class SecurityTests(unittest.TestCase):
    def test_pinned_discovery(self):
        issuer="https://tenant.auth0.com"
        seen=[]
        def fetch(url):
            seen.append(url)
            if url.endswith("openid-configuration"):
                return {"issuer":issuer+"/","jwks_uri":issuer+"/.well-known/jwks.json"}
            return {"keys":[{"kty":"RSA","kid":"synthetic"}]}
        verifier=load_auth0_verifier(issuer,"client-id",fetch=fetch)
        self.assertEqual(verifier.issuer,issuer+"/")
        self.assertEqual(len(seen),2)
    def test_jwks_redirect_denied(self):
        issuer="https://tenant.auth0.com"
        with self.assertRaises(PermissionError):
            load_auth0_verifier(issuer,"client",fetch=lambda url: {"issuer":issuer+"/","jwks_uri":"https://evil.example/jwks"})
    def test_state_missing_factory_denied(self):
        with self.assertRaises(ValueError): PostgresPKCEStateStore(None)
    def test_invalid_state_denied(self):
        store=PostgresPKCEStateStore(lambda: None)
        self.assertIsNone(store.consume("not-a-hash"))
        with self.assertRaises(ValueError): store.put("invalid",{},300)

if __name__=="__main__": unittest.main()
