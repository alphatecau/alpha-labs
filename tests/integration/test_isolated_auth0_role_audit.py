"""Contract tests for the fail-closed isolated staging role auditor."""
import unittest

from deployment.isolated_auth0_role_audit import audit_runtime_roles


class IsolatedRoleAuditTests(unittest.TestCase):
    def test_rejects_shared_runtime_roles(self):
        with self.assertRaises(ValueError):
            audit_runtime_roles(
                lambda: None, oauth_role="alpha_runtime",
                session_role="alpha_runtime", ownership_role="alpha_owner")

    def test_rejects_invalid_role_identifier(self):
        with self.assertRaises(ValueError):
            audit_runtime_roles(
                lambda: None, oauth_role="postgres; DROP TABLE x",
                session_role="alpha_sessions", ownership_role="alpha_owner")

    def test_rejects_missing_audit_connection(self):
        with self.assertRaises(ValueError):
            audit_runtime_roles(
                None, oauth_role="alpha_oauth",
                session_role="alpha_sessions", ownership_role="alpha_owner")


if __name__ == "__main__":
    unittest.main()
