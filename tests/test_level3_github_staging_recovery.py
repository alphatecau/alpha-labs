"""Non-destructive Level 3 recovery report tests."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools/level3_staging"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("github_staging_recovery", TOOLS / "github_staging_recovery.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.file = self.root / "docs/level3-staging/recovery.md"
        self.file.parent.mkdir(parents=True)
        self.file.write_bytes(b"expected")
        from github_staging_audit import record
        record(self.root, "created", "completed", "a" * 40,
               "docs/level3-staging/recovery.md",
               new_sha=hashlib.sha256(b"expected").hexdigest())

    def test_consistent(self):
        self.assertEqual(module.recovery_report(self.root)["status"], "consistent")

    def test_changed_file_is_reported_without_repair(self):
        self.file.write_bytes(b"changed")
        report = module.recovery_report(self.root)
        self.assertEqual(report["status"], "attention_required")
        self.assertEqual(report["affected_files"][0]["status"], "mismatch")
        self.assertEqual(self.file.read_bytes(), b"changed")

    def test_missing_file_is_reported_without_repair(self):
        self.file.unlink()
        report = module.recovery_report(self.root)
        self.assertEqual(report["affected_files"][0]["status"], "missing")
        self.assertFalse(self.file.exists())


if __name__ == "__main__":
    unittest.main()
