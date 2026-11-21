"""Local journal regression tests for Level 3 operator actions."""
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools/level3_staging"
sys.path.insert(0, str(TOOLS))


class AuditTests(unittest.TestCase):
    def test_append_and_read(self):
        from github_staging_audit import read_entries, record
        with tempfile.TemporaryDirectory() as root:
            record(root, "created", "completed", "a" * 40,
                   "docs/level3-staging/test.md", new_sha="b" * 64)
            record(root, "updated", "completed", "c" * 40,
                   "docs/level3-staging/test.md", old_sha="b" * 64, new_sha="d" * 64)
            events = read_entries(root)
            self.assertEqual([e["operation"] for e in events], ["created", "updated"])
            self.assertEqual(events[-1]["old_sha256"], "b" * 64)
            self.assertEqual(events[-1]["new_sha256"], "d" * 64)

    def test_symlink_audit_directory_refused(self):
        from github_staging_audit import record
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / ".level3-audit").symlink_to(Path(root))
            with self.assertRaises(OSError):
                record(root, "created", "completed", "a" * 40, "docs/level3-staging/test.md")


if __name__ == "__main__":
    unittest.main()
