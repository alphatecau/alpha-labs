"""Offline secret-provider rotation tests using synthetic credentials only."""
import json
import os
import tempfile
import unittest
from deployment.mounted_tenant_secret_provider import MountedTenantSecretProvider


OWNER = "oidc_" + "a" * 64


class MountedSecretTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = self.tmp.name + "/secrets.json"
        self.provider = MountedTenantSecretProvider(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, password, mode=0o600):
        payload = {"schema_version": 1, "accounts": {OWNER: {
            "host": "db.example", "port": 5432, "dbname": "research",
            "user": "alpha_tenant_a", "password": password}}}
        next_path = self.path + ".next"
        with open(next_path, "w", encoding="utf8") as stream:
            json.dump(payload, stream)
        os.chmod(next_path, mode)
        os.replace(next_path, self.path)

    def test_atomic_rotation_reload(self):
        self.write("synthetic-old")
        self.assertEqual(self.provider(OWNER)["password"], "synthetic-old")
        self.write("synthetic-new")
        self.assertEqual(self.provider(OWNER)["password"], "synthetic-new")

    def test_reject_unknown_and_bad_permissions(self):
        self.write("synthetic")
        with self.assertRaises(PermissionError):
            self.provider("oidc_" + "b" * 64)
        os.chmod(self.path, 0o644)
        with self.assertRaises(PermissionError):
            self.provider(OWNER)

    def test_reject_symlink(self):
        self.write("synthetic")
        link = self.tmp.name + "/link"
        os.symlink(self.path, link)
        with self.assertRaises(OSError):
            MountedTenantSecretProvider(link)(OWNER)


if __name__ == "__main__":
    unittest.main()
