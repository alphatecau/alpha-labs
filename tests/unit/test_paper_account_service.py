import tempfile
import unittest
from alpha_lab.research.paper_account_service import PaperAccountService, VerifiedPrincipal
from alpha_lab.research.paper_first_authority import TradingAuthority


class PaperAccountServiceTests(unittest.TestCase):
    def test_isolated_accounts_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            service = PaperAccountService(root)
            alice = VerifiedPrincipal("alice", "trusted-issuer")
            bob = VerifiedPrincipal("bob", "trusted-issuer")
            try:
                with self.assertRaises(PermissionError):
                    service.open_account(None, "primary")
                with self.assertRaises(PermissionError):
                    service.open_account(alice, "../escape")
                service.open_account(alice, "primary")
                with self.assertRaises(PermissionError):
                    service.status(bob, "primary")
                service.open_account(bob, "primary")
                self.assertTrue(service.status(bob, "primary")["halted"])
                with self.assertRaises(PermissionError):
                    service.enable_paper(alice, "primary", authority=TradingAuthority(),
                                         operator_approved=True)
                service.enable_paper(alice, "primary",
                                     authority=TradingAuthority(emergency_halt=False),
                                     operator_approved=True)
                self.assertFalse(service.status(alice, "primary")["halted"])
                self.assertTrue(service.status(bob, "primary")["halted"])
            finally:
                service.close()

    def test_reject_untrusted_identity_shapes(self):
        with tempfile.TemporaryDirectory() as root:
            service = PaperAccountService(root)
            try:
                for principal in ({"subject": "alice", "issuer": "trusted"}, "alice",
                                  VerifiedPrincipal("alice/other", "trusted"),
                                  VerifiedPrincipal("alice", "")):
                    with self.subTest(principal=principal), self.assertRaises(PermissionError):
                        service.open_account(principal, "primary")
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
