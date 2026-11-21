"""Offline tests for Level 3 prototype; no network or MCP activation."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from tools.level3_staging.controlled_write import Refused, apply, digest, propose

class TestStagingWrite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "workspace"
        (self.root / "docs/level3-staging").mkdir(parents=True)
        (self.root / "tests/level3-staging").mkdir(parents=True)
        self.approval = Path(self.tmp.name) / "approval.json"
        self.audit = Path(self.tmp.name) / "audit.jsonl"
        self.path = "docs/level3-staging/demo.md"

    def approve(self, content="hello", expires=1100):
        self.approval.write_text(json.dumps({"operation":"create","path":self.path,"sha256":digest(content),"expires_at":expires}))
        self.approval.chmod(0o600)

    def test_proposal(self):
        self.assertEqual(propose(self.root, self.path, "hello")["bytes"], 5)

    def test_create(self):
        self.approve()
        apply(self.root, self.path, "hello", self.approval, self.audit, now=1000)
        self.assertEqual((self.root / self.path).read_text(), "hello")
        self.assertTrue(Path(str(self.approval) + ".consumed").exists())

    def test_replay(self):
        self.approve()
        apply(self.root, self.path, "hello", self.approval, self.audit, now=1000)
        with self.assertRaises((Refused, FileNotFoundError)):
            apply(self.root, self.path, "hello", self.approval, self.audit, now=1000)

    def test_android_atomic_create_and_replay(self):
        self.approve()
        with mock.patch.object(os, "link", create=True):
            # Force the Android code path even on CPython builds with os.link.
            with mock.patch("tools.level3_staging.controlled_write.hasattr",
                            side_effect=lambda obj, key: False if obj is os and key == "link" else hasattr(obj, key), create=True):
                apply(self.root, self.path, "hello", self.approval, self.audit, now=1000)
        self.assertEqual((self.root / self.path).read_text(), "hello")
        self.assertFalse(self.approval.exists())
        self.assertTrue(Path(str(self.approval) + ".consumed").exists())
        with self.assertRaises((Refused, FileNotFoundError)):
            apply(self.root, self.path, "hello", self.approval, self.audit, now=1000)

    def test_android_atomic_no_replace(self):
        self.approve()
        consumed = Path(str(self.approval) + ".consumed")
        consumed.write_text("prior")
        with mock.patch("tools.level3_staging.controlled_write.hasattr",
                        side_effect=lambda obj, key: False if obj is os and key == "link" else hasattr(obj, key), create=True):
            with self.assertRaises(Refused):
                apply(self.root, self.path, "hello", self.approval, self.audit, now=1000)
        self.assertEqual(consumed.read_text(), "prior")
        self.assertTrue(self.approval.exists())
        self.assertFalse((self.root / self.path).exists())

    def test_traversal(self):
        with self.assertRaises(Refused):
            propose(self.root, "docs/level3-staging/../bad.md", "x")

    def test_nested(self):
        with self.assertRaises(Refused):
            propose(self.root, "docs/level3-staging/nested/bad.md", "x")

    def test_symlink_directory(self):
        (self.root / "docs/level3-staging").rename(self.root / "docs/renamed")
        (self.root / "docs/level3-staging").symlink_to(self.root / "docs/renamed")
        with self.assertRaises(OSError):
            propose(self.root, self.path, "x")

    def test_symlink_file(self):
        (self.root / self.path).symlink_to(self.approval)
        with self.assertRaises(Refused):
            propose(self.root, self.path, "x")

    def test_existing(self):
        (self.root / self.path).write_text("old")
        with self.assertRaises(Refused):
            propose(self.root, self.path, "new")

    def test_wrong_content(self):
        self.approve()
        with self.assertRaises(Refused):
            apply(self.root, self.path, "different", self.approval, self.audit, now=1000)

    def test_expired(self):
        self.approve(expires=999)
        with self.assertRaises(Refused):
            apply(self.root, self.path, "hello", self.approval, self.audit, now=1000)

    def test_permissions(self):
        self.approve()
        self.approval.chmod(0o644)
        with self.assertRaises(Refused):
            apply(self.root, self.path, "hello", self.approval, self.audit, now=1000)

    def test_size(self):
        with self.assertRaises(Refused):
            propose(self.root, self.path, "x" * 32769)

    def test_audit_symlink(self):
        self.approve()
        self.audit.symlink_to(self.approval)
        with self.assertRaises(Refused):
            apply(self.root, self.path, "hello", self.approval, self.audit, now=1000)

    def test_consumed_block(self):
        self.approve()
        Path(str(self.approval) + ".consumed").write_text("old")
        with self.assertRaises(Refused):
            apply(self.root, self.path, "hello", self.approval, self.audit, now=1000)

if __name__ == "__main__":
    unittest.main()
