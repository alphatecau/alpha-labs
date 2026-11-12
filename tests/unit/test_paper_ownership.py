import tempfile
import unittest
from pathlib import Path
from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.paper_ownership import PaperOwnershipRegistry


class OwnershipTests(unittest.TestCase):
    def test_persistence_isolation_and_revocation(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "owners.sqlite3"
            alice = VerifiedPrincipal("alice", "issuer")
            bob = VerifiedPrincipal("bob", "issuer")
            registry = PaperOwnershipRegistry(path)
            try:
                registry.provision(alice, "primary")
                self.assertTrue(registry.authorised(alice, "primary"))
                self.assertFalse(registry.authorised(bob, "primary"))
            finally:
                registry.close()
            registry = PaperOwnershipRegistry(path)
            try:
                self.assertTrue(registry.authorised(alice, "primary"))
                registry.revoke(alice, "primary")
                self.assertFalse(registry.authorised(alice, "primary"))
                registry.provision(alice, "primary")
                self.assertFalse(registry.authorised(alice, "primary"))
                with self.assertRaises(PermissionError):
                    registry.authorised(VerifiedPrincipal("../alice", "issuer"), "primary")
            finally:
                registry.close()


if __name__ == "__main__":
    unittest.main()
