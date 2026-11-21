"""Single-use approval ledger regression tests."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools/level3_staging"
spec = importlib.util.spec_from_file_location("approval_replay", TOOLS / "approval_replay.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "replay.sqlite"

    def test_single_use(self):
        self.assertEqual(module.consume(self.db, "a" * 32, "b" * 64)["status"], "consumed")
        with self.assertRaises(module.ReplayDenied):
            module.consume(self.db, "a" * 32, "b" * 64)

    def test_replay_persists(self):
        module.consume(self.db, "c" * 32, "d" * 64)
        with self.assertRaises(module.ReplayDenied):
            module.consume(self.db, "c" * 32, "e" * 64)

    def test_bad_nonce(self):
        with self.assertRaises(module.ReplayDenied):
            module.consume(self.db, "../", "b" * 64)

    def test_bad_digest(self):
        with self.assertRaises(module.ReplayDenied):
            module.consume(self.db, "a" * 32, "invalid")

    def test_symlink_db_refused(self):
        target = Path(self.temp.name) / "target"
        target.write_text("unchanged")
        self.db.symlink_to(target)
        with self.assertRaises(module.ReplayDenied):
            module.consume(self.db, "a" * 32, "b" * 64)
        self.assertEqual(target.read_text(), "unchanged")


if __name__ == "__main__":
    unittest.main()
