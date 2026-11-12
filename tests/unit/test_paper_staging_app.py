import base64
import tempfile
import unittest
from pathlib import Path
from alpha_lab.research.paper_staging_app import build_app
from alpha_lab.research.paper_identity import PaperIdentityVerifier


class StagingAppTests(unittest.TestCase):
    def test_missing_config_and_weak_key_fail_closed(self):
        with self.assertRaises(RuntimeError):
            build_app({})
        with tempfile.TemporaryDirectory() as root:
            config = dict(ALPHA_PAPER_SIGNING_KEY_B64=base64.b64encode(b"short").decode(),
                          ALPHA_PAPER_ISSUER="trusted", ALPHA_PAPER_AUDIENCE="paper",
                          ALPHA_PAPER_DATA_DIR=root, ALPHA_PAPER_OWNER_SUBJECT="alice")
            with self.assertRaises(RuntimeError):
                build_app(config)
            config["ALPHA_PAPER_SIGNING_KEY_B64"] = base64.b64encode(b"x" * 32).decode()
            app = build_app(config)
            self.assertIsInstance(app.verifier, PaperIdentityVerifier)
            self.assertTrue(app.accounts.status(
                __import__("alpha_lab.research.paper_account_service", fromlist=["VerifiedPrincipal"])
                .VerifiedPrincipal("alice", "trusted"), "primary")["halted"])
            app.accounts.close()

    def test_missing_storage_and_invalid_subject_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            config = dict(ALPHA_PAPER_SIGNING_KEY_B64=base64.b64encode(b"x" * 32).decode(),
                          ALPHA_PAPER_ISSUER="trusted", ALPHA_PAPER_AUDIENCE="paper",
                          ALPHA_PAPER_DATA_DIR=str(Path(root) / "missing"),
                          ALPHA_PAPER_OWNER_SUBJECT="alice")
            with self.assertRaises(RuntimeError):
                build_app(config)
            config["ALPHA_PAPER_DATA_DIR"] = root
            config["ALPHA_PAPER_OWNER_SUBJECT"] = "../alice"
            with self.assertRaises(PermissionError):
                build_app(config)


if __name__ == "__main__":
    unittest.main()
