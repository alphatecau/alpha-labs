import json
import unittest
from deployment.render_environment_tenant_secrets import RenderEnvironmentTenantSecrets

A = "oidc_" + "a" * 64
B = "oidc_" + "b" * 64


class RenderSecretsTests(unittest.TestCase):
    def setUp(self):
        self.env = {}
        self.provider = RenderEnvironmentTenantSecrets(self.env)
        self.credentials = {"host": "db.internal", "port": 5432, "dbname": "alpha_test",
                            "user": "alpha_tenant_a", "password": "synthetic-old"}

    def publish(self):
        self.env["ALPHA_TENANT_CREDENTIALS_JSON"] = json.dumps(
            {"schema_version": 1, "accounts": {A: self.credentials}})

    def test_valid_and_restart_rotation_configuration(self):
        self.publish()
        self.assertEqual(self.provider(A)["password"], "synthetic-old")
        self.credentials["password"] = "synthetic-new"
        self.publish()
        self.assertEqual(self.provider(A)["password"], "synthetic-new")

    def test_missing_and_cross_tenant_denied(self):
        with self.assertRaises(PermissionError):
            self.provider(A)
        self.publish()
        with self.assertRaises(PermissionError):
            self.provider(B)
        with self.assertRaises(PermissionError):
            self.provider("postgres")

    def test_malformed_and_superuser_denied(self):
        self.env["ALPHA_TENANT_CREDENTIALS_JSON"] = "{"
        with self.assertRaises(PermissionError):
            self.provider(A)
        self.credentials["user"] = "postgres"
        self.publish()
        with self.assertRaises(PermissionError):
            self.provider(A)

    def test_never_accept_browser_supplied_account(self):
        self.publish()
        with self.assertRaises(PermissionError):
            self.provider(A + "?account=" + B)


if __name__ == "__main__":
    unittest.main()
