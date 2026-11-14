import unittest
from deployment.auth0_login_flow import Auth0LoginFlow
from deployment.tenant_credential_broker import TenantCredentialBroker


class Store:
    def __init__(self): self.data = {}
    def put(self, key, value, ttl): self.data[key] = value
    def consume(self, key): return self.data.pop(key, None)


class SecurityPreparationTests(unittest.TestCase):
    def test_auth0_pkce_and_one_use_nonce(self):
        store = Store()
        flow = Auth0LoginFlow(issuer="https://tenant.auth0.com", client_id="client",
                             redirect_uri="https://dashboard.example/callback",
                             state_store=store, clock=lambda: 1000)
        from urllib.parse import urlsplit, parse_qs
        params = parse_qs(urlsplit(flow.begin()).query)
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertNotIn("code_verifier", params)
        state = params["state"][0]
        nonce = params["nonce"][0]
        result = flow.validate_callback(state=state, code="synthetic-code",
                   id_token="synthetic-token", verifier=lambda token: {"verified": True, "nonce": nonce})
        self.assertTrue(result["pkce_verifier"])
        with self.assertRaises(PermissionError):
            flow.validate_callback(state=state, code="synthetic-code",
                id_token="synthetic-token", verifier=lambda token: {"verified": True, "nonce": nonce})

    def test_auth0_wrong_nonce_denied(self):
        flow = Auth0LoginFlow(issuer="https://tenant.auth0.com", client_id="client",
                             redirect_uri="https://dashboard.example/callback",
                             state_store=Store(), clock=lambda: 1000)
        from urllib.parse import urlsplit, parse_qs
        state = parse_qs(urlsplit(flow.begin()).query)["state"][0]
        with self.assertRaises(PermissionError):
            flow.validate_callback(state=state, code="code", id_token="token",
                                   verifier=lambda token: {"verified": True, "nonce": "forged"})

    def test_broker_fails_closed_without_credentials(self):
        broker = TenantCredentialBroker(lambda owner: None,
                                        lambda **kwargs: self.fail("must not connect"))
        with self.assertRaises(PermissionError):
            with broker("oidc_valid"): pass

    def test_broker_rejects_superuser_and_missing_read_only(self):
        class Cursor:
            def __init__(self, readonly): self.n = 0; self.readonly = readonly
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def execute(self, sql): self.n += 1
            def fetchone(self):
                if self.n == 1: return ("alpha_tenant_a", True, False, False)
                return ("on" if self.readonly else "off",)
        class Connection:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def cursor(self): return Cursor(True)
        broker = TenantCredentialBroker(
            lambda owner: {"host": "db.example", "port": 5432, "dbname": "research",
                           "user": "alpha_tenant_a", "password": "synthetic"},
            lambda **kwargs: Connection())
        with self.assertRaises(PermissionError):
            with broker("oidc_valid"): pass


if __name__ == "__main__": unittest.main()
