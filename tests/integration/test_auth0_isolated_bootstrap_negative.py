"""Offline fail-closed isolated staging bootstrap checks; no Render credentials."""
import unittest

from deployment.isolated_auth0_wsgi import build_isolated_app


class IsolatedStagingBootstrapTests(unittest.TestCase):
    def test_isolated_flag_is_required(self):
        with self.assertRaises(PermissionError):
            build_isolated_app({})

    def test_missing_secret_rejected_before_network(self):
        with self.assertRaises(PermissionError):
            build_isolated_app({"ALPHA_ISOLATED_STAGING": "true"})

    def test_existing_render_host_is_forbidden(self):
        config = {key: "placeholder" for key in (
            "AUTH0_ISSUER", "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET",
            "ALPHA_OAUTH_DSN", "ALPHA_SESSION_DSN", "ALPHA_OWNERSHIP_DSN",
            "ALPHA_AUDIT_DSN", "ALPHA_OAUTH_ROLE", "ALPHA_SESSION_ROLE",
            "ALPHA_OWNERSHIP_ROLE", "ALPHA_TENANT_CREDENTIALS_JSON")}
        config.update(ALPHA_ISOLATED_STAGING="true",
                      ALPHA_STAGING_ORIGIN="https://alpha-labs-k869.onrender.com")
        with self.assertRaises(PermissionError):
            build_isolated_app(config)

    def test_same_database_credential_rejected(self):
        config = {key: "placeholder" for key in (
            "AUTH0_ISSUER", "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET",
            "ALPHA_OAUTH_DSN", "ALPHA_SESSION_DSN", "ALPHA_OWNERSHIP_DSN",
            "ALPHA_AUDIT_DSN", "ALPHA_OAUTH_ROLE", "ALPHA_SESSION_ROLE",
            "ALPHA_OWNERSHIP_ROLE", "ALPHA_TENANT_CREDENTIALS_JSON")}
        config.update(ALPHA_ISOLATED_STAGING="true",
                      ALPHA_STAGING_ORIGIN="https://isolated.example")
        with self.assertRaises(PermissionError):
            build_isolated_app(config)


if __name__ == "__main__":
    unittest.main()
