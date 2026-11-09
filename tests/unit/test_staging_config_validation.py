import unittest
from alpha_lab.research.staging_config_validation import (
    StagingConfigurationError, validate_staging_configuration)


class StagingConfigurationTests(unittest.TestCase):
    def config(self, **overrides):
        data = dict(expected_origin="https://staging.example.com",
                    callback_uri="https://staging.example.com/auth/callback",
                    issuer="https://tenant.example.com/",
                    trusted_peer_cidrs=("10.12.0.0/24",),
                    database_dsn_present=True, oidc_client_id_present=True,
                    oidc_secret_present=True)
        data.update(overrides)
        return validate_staging_configuration(**data)

    def test_configuration_is_never_automatic_deployment_approval(self):
        result = self.config(verified_ingress_peer=True,
                             verified_account_backend=True)
        self.assertFalse(result["ready_for_deployment"])
        self.assertTrue(result["all_prerequisites_reported"])
        self.assertEqual(result["trading"], "DISABLED")

    def test_missing_external_evidence_blocks_readiness(self):
        result = self.config()
        self.assertFalse(result["all_prerequisites_reported"])
        self.assertFalse(result["gates"]["ingress_peer_independently_verified"])

    def test_missing_credentials_or_database_blocks(self):
        for key in ("database_dsn_present", "oidc_client_id_present", "oidc_secret_present"):
            with self.subTest(key=key):
                self.assertFalse(self.config(**{key: False})["all_prerequisites_reported"])

    def test_untrusted_cidr_and_invalid_urls_fail_closed(self):
        for cidr in ("0.0.0.0/0", "::/0", "127.0.0.1/32",
                     "8.8.8.8/32", "10.0.0.1/24", "bad"):
            with self.subTest(cidr=cidr):
                with self.assertRaises(StagingConfigurationError):
                    self.config(trusted_peer_cidrs=(cidr,))
        for kw in ({"expected_origin": "http://staging.example.com"},
                   {"callback_uri": "https://evil.example/auth/callback"},
                   {"callback_uri": "https://staging.example.com/auth/callback?x=1"},
                   {"issuer": "http://tenant.example.com/"},
                   {"expected_origin": "https://user:password@staging.example.com"}):
            with self.subTest(kw=kw):
                with self.assertRaises(StagingConfigurationError):
                    self.config(**kw)


if __name__ == "__main__":
    unittest.main()
