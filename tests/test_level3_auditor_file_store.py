import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.level3_staging.auditor_file_store import AuditorFileStore, AuditorStoreDenied


class AuditorFileStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "auditor"
        self.root.mkdir(mode=0o700)
        self.store = AuditorFileStore(self.root)
        self.audience = "alpha-labs-level3:staging"
        self.key = "level3-checkpoints/alpha-labs-level3_staging/" + "0" * 20 + "-" + "a" * 64 + ".json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_once_readback_and_no_overwrite(self):
        self.store.create_once(self.key, b"checkpoint")
        self.assertEqual(self.store.read(self.key), b"checkpoint")
        with self.assertRaises(FileExistsError):
            self.store.create_once(self.key, b"rewrite")
        self.assertEqual(self.store.read(self.key), b"checkpoint")

    def test_atomic_latest_cas(self):
        a = {"receipt": {"head_hash": "a"}}
        b = {"receipt": {"head_hash": "b"}}
        self.assertTrue(self.store.advance_latest(self.audience, None, a))
        self.assertFalse(self.store.advance_latest(self.audience, None, b))
        self.assertTrue(self.store.advance_latest(self.audience, a["receipt"], b))
        self.assertEqual(self.store.read_latest(self.audience), b)
        self.assertFalse(self.store.advance_latest(self.audience, a["receipt"], a))

    def test_path_traversal_denied(self):
        with self.assertRaises(AuditorStoreDenied):
            self.store.create_once("../escape", b"test")

    def test_world_readable_root_denied(self):
        os.chmod(self.root, 0o755)
        with self.assertRaises(AuditorStoreDenied):
            AuditorFileStore(self.root)


if __name__ == "__main__":
    unittest.main()
