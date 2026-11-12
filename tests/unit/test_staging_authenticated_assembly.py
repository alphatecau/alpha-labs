"""Staging assembly fails closed without credentials or trusted dependencies."""
import unittest
from deployment.staging_authenticated_assembly import assemble

class AssemblyTests(unittest.TestCase):
    def test_missing_configuration_denied(self):
        with self.assertRaises(ValueError):
            assemble(verify_token=lambda t: None, ownership=object(),
                     principal_factory=lambda **kw: kw, state_store=object(),
                     session_connect=lambda: None, tenant_connect=lambda **kw: None, rate_limiter=None,
                     environ={})
    def test_missing_confidential_secret_denied(self):
        config={"AUTH0_ISSUER":"https://tenant.auth0.com/",
                "AUTH0_CLIENT_ID":"synthetic-client",
                "AUTH0_CALLBACK_URL":"https://staging.example/auth/callback",
                "ALPHA_BFF_ORIGIN":"https://staging.example"}
        with self.assertRaises(ValueError):
            assemble(verify_token=lambda t: None, ownership=object(),
                     principal_factory=lambda **kw: kw, state_store=object(),
                     session_connect=lambda: None, tenant_connect=lambda **kw: None, rate_limiter=None,
                     environ=config)

if __name__=="__main__": unittest.main()
