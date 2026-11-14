"""Offline, non-deploying staging guardrails for isolated Auth0 BFF."""
import unittest
from unittest.mock import patch

from deployment.isolated_auth0_wsgi import build_isolated_app
from deployment.staging_authenticated_bff import StagingResearchBFF


class IsolatedStagingReadinessTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "ALPHA_ISOLATED_STAGING": "true",
            "AUTH0_ISSUER": "https://tenant.example.auth0.com/",
            "AUTH0_CLIENT_ID": "non-secret-test-client",
            "AUTH0_CLIENT_SECRET": "test-placeholder-only",
            "ALPHA_STAGING_ORIGIN": "https://isolated-staging.example",
            "ALPHA_OAUTH_DSN": "oauth-test",
            "ALPHA_SESSION_DSN": "session-test",
            "ALPHA_OWNERSHIP_DSN": "ownership-test",
            "ALPHA_AUDIT_DSN": "audit-test",
            "ALPHA_OAUTH_ROLE": "oauth_restricted",
            "ALPHA_SESSION_ROLE": "session_restricted",
            "ALPHA_OWNERSHIP_ROLE": "ownership_restricted",
            "ALPHA_TENANT_CREDENTIALS_JSON": "{}",
        }

    def assert_refused_without_network(self, config):
        def forbidden(*args, **kwargs):
            self.fail("database connection attempted before isolation validation")
        with self.assertRaises(PermissionError):
            build_isolated_app(config, pg_connect=forbidden)

    def test_isolation_flag_required(self):
        for value in ("false", "", "TRUE"):
            with self.subTest(value=value):
                config = dict(self.config, ALPHA_ISOLATED_STAGING=value)
                self.assert_refused_without_network(config)

    def test_every_required_setting_is_mandatory(self):
        for key in self.config:
            with self.subTest(key=key):
                config = dict(self.config)
                config.pop(key)
                self.assert_refused_without_network(config)

    def test_production_health_service_hostname_refused(self):
        config = dict(self.config, ALPHA_STAGING_ORIGIN="https://alpha-labs-k869.onrender.com")
        self.assert_refused_without_network(config)

    def test_non_https_and_non_origin_urls_refused(self):
        for origin in ("http://isolated.example", "https://isolated.example/path",
                       "https://isolated.example/?query=1", "https://user@isolated.example"):
            with self.subTest(origin=origin):
                self.assert_refused_without_network(dict(self.config, ALPHA_STAGING_ORIGIN=origin))

    def test_shared_runtime_credentials_refused(self):
        for key in ("ALPHA_SESSION_DSN", "ALPHA_OWNERSHIP_DSN", "ALPHA_AUDIT_DSN"):
            with self.subTest(key=key):
                self.assert_refused_without_network(dict(self.config, **{key: self.config["ALPHA_OAUTH_DSN"]}))

    def test_invalid_tenant_mapping_refused_before_database_access(self):
        self.assert_refused_without_network(dict(self.config, ALPHA_TENANT_CREDENTIALS_JSON="[]"))

    def test_import_does_not_bootstrap_service(self):
        # A passive import or health probe must not bypass isolated staging approval.
        with patch("deployment.isolated_auth0_wsgi.build_isolated_app",
                   side_effect=PermissionError("staging disabled")):
            from deployment import isolated_auth0_wsgi
            previous = isolated_auth0_wsgi._app
            isolated_auth0_wsgi._app = None
            try:
                with self.assertRaises(PermissionError):
                    isolated_auth0_wsgi.application({"PATH_INFO": "/healthz"}, lambda *args: None)
            finally:
                isolated_auth0_wsgi._app = previous

    def test_bff_health_is_research_only(self):
        class NoReader:
            pass
        # Validate the published health response without constructing a privileged reader.
        app = object.__new__(StagingResearchBFF)
        headers = []
        body = b"".join(app({"PATH_INFO": "/healthz", "REQUEST_METHOD": "GET"},
                            lambda status, fields: headers.append((status, fields))))
        self.assertEqual(headers[0][0], "200 OK")
        self.assertEqual(body, b'{"status":"ok","trading":"disabled"}')


if __name__ == "__main__":
    unittest.main()
