"""Synthetic tenant-credential isolation fixtures; no database or credentials used."""

import json
import unittest
from contextlib import nullcontext
from deployment.render_environment_tenant_secrets import RenderEnvironmentTenantSecrets
from deployment.tenant_credential_broker import (
    TenantCredentialBroker,
    tenant_login_role,
)


class Cursor:
    def __init__(self, role):
        self.role = role
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, args=()):
        self.query, self.args = sql, args

    def fetchone(self):
        if "pg_auth_members" in self.query:
            return (self.args == (self.role,),)
        if self.query.startswith("SHOW"):
            return ("on",)
        return (True,)


class Conn:
    def __init__(self, role):
        self.role = role

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return Cursor(self.role)

    def transaction(self):
        return nullcontext()


class TenantFixtureTests(unittest.TestCase):
    def setUp(self):
        self.alice = "oidc_" + "a" * 64
        self.bob = "oidc_" + "b" * 64

        def cred(role):
            return dict(
                host="db.invalid",
                port=5432,
                dbname="alpha_rls_test",
                user=role,
                password="synthetic-only",
            )

        self.env = {
            "ALPHA_TENANT_CREDENTIALS_JSON": json.dumps(
                {
                    "schema_version": 1,
                    "accounts": {
                        self.alice: cred(tenant_login_role(self.alice)),
                        self.bob: cred(tenant_login_role(self.bob)),
                    },
                }
            )
        }
        self.calls = []

        def connect(**kwargs):
            self.calls.append(kwargs)
            return Conn(kwargs["user"])

        self.broker = TenantCredentialBroker(
            RenderEnvironmentTenantSecrets(self.env), connect
        )

    def test_distinct_verified_owners_get_distinct_roles(self):
        with self.broker(self.alice):
            pass
        with self.broker(self.bob):
            pass
        self.assertEqual(
            [c["user"] for c in self.calls],
            [tenant_login_role(self.alice), tenant_login_role(self.bob)],
        )
        self.assertTrue(all(c["sslmode"] == "verify-full" for c in self.calls))

    def test_unprovisioned_or_spoofed_owner_denied(self):
        for owner in ("oidc_" + "c" * 64, "alpha_tenant_bob", "", None):
            with self.subTest(owner=owner):
                with self.assertRaises(PermissionError):
                    with self.broker(owner):
                        pass
        self.assertEqual(self.calls, [])

    def test_role_mismatch_denied(self):
        self.broker = TenantCredentialBroker(
            RenderEnvironmentTenantSecrets(self.env),
            lambda **kw: Conn(tenant_login_role(self.bob)),
        )
        with self.assertRaises(PermissionError):
            with self.broker(self.alice):
                pass

    def test_missing_secrets_denied(self):
        self.env.clear()
        with self.assertRaises(PermissionError):
            with self.broker(self.alice):
                pass


if __name__ == "__main__":
    unittest.main()
