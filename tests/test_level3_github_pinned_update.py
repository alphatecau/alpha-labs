"""Offline tests for pinned GitHub staging updates."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools/level3_staging"
sys.path.insert(0, str(TOOLS))
import importlib.util

spec = importlib.util.spec_from_file_location("github_pinned_update", TOOLS / "github_pinned_update.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
update = module.update

COMMIT = "a" * 40
PATH = "docs/level3-staging/approved.md"

class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        target = self.root / PATH
        target.parent.mkdir(parents=True)
        target.write_bytes(b"before")
        self.old = hashlib.sha256(b"before").hexdigest()
        self.new = hashlib.sha256(b"after").hexdigest()

    def apply(self, old=None, new=None, path=PATH):
        return update(self.root, COMMIT, path, old or self.old, new or self.new,
                      fetcher=lambda *_: b"after")

    def test_update_success(self):
        self.assertEqual(self.apply()["status"], "updated")
        self.assertEqual((self.root / PATH).read_bytes(), b"after")

    def test_stale_old_hash_refused(self):
        with self.assertRaises(ValueError):
            self.apply(old="0" * 64)
        self.assertEqual((self.root / PATH).read_bytes(), b"before")

    def test_wrong_new_hash_refused(self):
        with self.assertRaises(ValueError):
            self.apply(new="0" * 64)
        self.assertEqual((self.root / PATH).read_bytes(), b"before")

    def test_missing_target_refused(self):
        with self.assertRaises(FileNotFoundError):
            self.apply(path="docs/level3-staging/missing.md")

    def test_symlink_target_refused(self):
        target = self.root / PATH
        target.unlink()
        target.symlink_to(self.root / "outside")
        with self.assertRaises(OSError):
            self.apply()

    def test_disallowed_path_refused(self):
        with self.assertRaises(ValueError):
            self.apply(path="../escape.md")

    def test_repeat_update_refused(self):
        self.apply()
        with self.assertRaises(ValueError):
            self.apply()

if __name__ == "__main__":
    unittest.main()
