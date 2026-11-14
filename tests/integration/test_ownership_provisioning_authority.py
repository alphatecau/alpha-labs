"""Fail-closed provisioning tests: a principal's shape is not identity proof."""
import unittest

from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.postgres_paper_security import PostgresPaperOwnership


class ProvisioningAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.principal = VerifiedPrincipal("alice", "https://issuer.example/")

    def test_unconfigured_authority_rejects_before_database(self):
        def forbidden_connect():
            self.fail("database must not be opened")
        with self.assertRaisesRegex(PermissionError, "verified provisioning authority"):
            PostgresPaperOwnership(forbidden_connect).provision(self.principal, "primary")

    def test_explicit_denial_rejects_before_database(self):
        def forbidden_connect():
            self.fail("database must not be opened")
        with self.assertRaisesRegex(PermissionError, "verified provisioning authority"):
            PostgresPaperOwnership(forbidden_connect, verify_provisioning_authority=lambda p: False).provision(self.principal, "primary")

    def test_truthy_nonboolean_is_not_approval(self):
        with self.assertRaises(PermissionError):
            PostgresPaperOwnership(lambda: self.fail("database must not be opened"),
                                   verify_provisioning_authority=lambda p: "yes").provision(self.principal, "primary")


if __name__ == "__main__":
    unittest.main()
