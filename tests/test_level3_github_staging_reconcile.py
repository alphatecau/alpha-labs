"""Read-only Level 3 audit reconciliation tests."""
import hashlib
import importlib.util
import sys
from pathlib import Path
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools/level3_staging"
spec = importlib.util.spec_from_file_location("github_staging_reconcile", TOOLS / "github_staging_reconcile.py")
sys.path.insert(0, str(TOOLS))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "docs/level3-staging/a.md"
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b"first")
        from github_staging_audit import record
        self.record = record
        self.record(self.root, "created", "completed", "a" * 40,
                    "docs/level3-staging/a.md", new_sha=hashlib.sha256(b"first").hexdigest())

    def test_matching_file(self):
        self.assertTrue(module.reconcile(self.root)["ok"])

    def test_changed_file(self):
        self.target.write_bytes(b"changed")
        result = module.reconcile(self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["files"][0]["status"], "mismatch")

    def test_missing_file(self):
        self.target.unlink()
        self.assertEqual(module.reconcile(self.root)["files"][0]["status"], "missing")

    def test_updated_hash_is_current(self):
        self.target.write_bytes(b"second")
        self.record(self.root, "updated", "completed", "b" * 40,
                    "docs/level3-staging/a.md",
                    old_sha=hashlib.sha256(b"first").hexdigest(),
                    new_sha=hashlib.sha256(b"second").hexdigest())
        self.assertTrue(module.reconcile(self.root)["ok"])


if __name__ == "__main__":
    unittest.main()
