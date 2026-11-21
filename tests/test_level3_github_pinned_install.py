"""Offline tests for operator-run GitHub pinned staging installation."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "tools/level3_staging/github_pinned_install.py"
spec = importlib.util.spec_from_file_location("github_pinned_install", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
COMMIT = "a" * 40

class PinnedInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "docs/level3-staging").mkdir(parents=True)
        (self.root / "tests/level3-staging").mkdir(parents=True)
        self.data = b"approved content\n"
        self.digest = hashlib.sha256(self.data).hexdigest()

    def apply(self, path="docs/level3-staging/approved.md", digest=None):
        return mod.install(self.root, COMMIT, path, digest or self.digest,
                           fetcher=lambda commit, name: self.data)

    def test_approved_create(self):
        self.assertEqual(self.apply()["status"], "created")
        self.assertEqual((self.root / "docs/level3-staging/approved.md").read_bytes(), self.data)

    def test_existing_file_never_overwritten(self):
        self.apply()
        with self.assertRaises(FileExistsError):
            self.apply()

    def test_digest_mismatch_denied(self):
        with self.assertRaises(ValueError):
            self.apply(digest="0" * 64)

    def test_traversal_denied(self):
        with self.assertRaises(ValueError):
            self.apply("../escape.md")

    def test_short_commit_denied(self):
        with self.assertRaises(ValueError):
            mod.install(self.root, "main", "docs/level3-staging/approved.md",
                        self.digest, fetcher=lambda *_: self.data)

    def test_symlink_parent_denied(self):
        (self.root / "docs/level3-staging").rmdir()
        (self.root / "docs/level3-staging").symlink_to(self.root / "tests/level3-staging")
        with self.assertRaises(OSError):
            self.apply()

    def test_oversize_denied(self):
        with self.assertRaises(ValueError):
            mod.install(self.root, COMMIT, "docs/level3-staging/approved.md",
                        hashlib.sha256(b"x" * 32769).hexdigest(),
                        fetcher=lambda *_: b"x" * 32769)

if __name__ == "__main__":
    unittest.main()
