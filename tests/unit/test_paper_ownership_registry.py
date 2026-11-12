import tempfile
import unittest

from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.paper_ownership_registry import PaperOwnershipRegistry


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = self.tmp.name + "/owners.db"
        self.reg = PaperOwnershipRegistry(self.path)
        self.alice = VerifiedPrincipal(
            subject="auth0_alice", issuer="https://tenant.example/"
        )
        self.bob = VerifiedPrincipal(
            subject="auth0_bob", issuer="https://tenant.example/"
        )

    def tearDown(self):
        self.reg.close()
        self.tmp.cleanup()

    def test_provision_is_explicit_and_owner_bound(self):
        with self.assertRaises(PermissionError):
            self.reg.require(self.alice, "primary")
        self.reg.provision(self.alice, "primary")
        self.assertTrue(self.reg.require(self.alice, "primary"))
        with self.assertRaises(PermissionError):
            self.reg.require(self.bob, "primary")
        with self.assertRaises(PermissionError):
            self.reg.require(self.alice, "secondary")

    def test_revoke_and_persist(self):
        self.reg.provision(self.alice, "primary")
        self.reg.close()
        self.reg = PaperOwnershipRegistry(self.path)
        self.assertTrue(self.reg.require(self.alice, "primary"))
        self.reg.revoke(self.alice, "primary")
        with self.assertRaises(PermissionError):
            self.reg.require(self.alice, "primary")

    def test_issuer_isolation_and_untrusted_principal(self):
        self.reg.provision(self.alice, "primary")
        other = VerifiedPrincipal(
            subject="auth0_alice", issuer="https://other.example/"
        )
        with self.assertRaises(PermissionError):
            self.reg.require(other, "primary")
        for bad in (
            None,
            {"subject": "auth0_alice", "issuer": "https://tenant.example/"},
        ):
            with self.assertRaises(PermissionError):
                self.reg.provision(bad, "primary")
        with self.assertRaises(PermissionError):
            self.reg.provision(self.alice, "../escape")


if __name__ == "__main__":
    unittest.main()
