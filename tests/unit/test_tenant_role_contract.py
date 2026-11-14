"""Synthetic restricted-role contract tests; no PostgreSQL access or mutations."""
import unittest
from deployment.tenant_credential_broker import TenantCredentialBroker, tenant_login_role, _LOGIN_CHECK, _TABLE_CHECK
from deployment.account_role_research_reader import AccountRoleResearchReader

A = "oidc_" + "a" * 64
B = "oidc_" + "b" * 64

class TenantRoleContractTests(unittest.TestCase):
    def test_roles_deterministic_and_distinct(self):
        self.assertNotEqual(tenant_login_role(A), tenant_login_role(B))
        self.assertLessEqual(len(tenant_login_role(A)), 63)

    def test_reject_unverified_owner(self):
        for value in ("", "alice", "oidc_" + "a" * 63, "oidc_" + "z" * 64, None):
            with self.subTest(value=value), self.assertRaises(PermissionError):
                tenant_login_role(value)

    def test_misbound_credentials_rejected_before_connection(self):
        def never_connect(**kwargs):
            self.fail("unsafe connection attempted")
        credentials = dict(host="localhost", port=5432, dbname="disposable", user=tenant_login_role(B), password="synthetic")
        reader = AccountRoleResearchReader(TenantCredentialBroker(lambda owner: credentials, never_connect))
        with self.assertRaises(PermissionError):
            reader.list_runs(A)

    def test_unprovisioned_rejected(self):
        reader = AccountRoleResearchReader(TenantCredentialBroker(lambda owner: None, lambda **kwargs: None))
        with self.assertRaises(PermissionError):
            reader.list_runs(A)

    def test_reader_requires_broker(self):
        with self.assertRaises(ValueError):
            AccountRoleResearchReader(lambda owner: None)

    def test_invalid_limit_rejected_before_connection(self):
        reader = AccountRoleResearchReader(TenantCredentialBroker(lambda owner: None, lambda **kwargs: None))
        for limit in (0, 51, True, "2"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                reader.list_runs(A, limit)

    def test_policy_contract_uses_session_identity(self):
        self.assertIn("SESSION_USER", _TABLE_CHECK)
        self.assertIn("relforcerowsecurity", _TABLE_CHECK)
        self.assertIn("rolbypassrls", _LOGIN_CHECK)
        self.assertIn("current_user = session_user", _LOGIN_CHECK)

if __name__ == "__main__":
    unittest.main()
