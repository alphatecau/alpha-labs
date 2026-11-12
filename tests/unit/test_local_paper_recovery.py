"""Android journal verification, backup and restore tests on disposable files."""
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from alpha_lab.research.live_paper_session import LivePaperSession
from alpha_lab.research.local_paper_recovery import (
    JOURNAL_NAME,
    backup_stopped_journal,
    prepare_working_copy,
    publish_verified_file,
    restore_backup,
    verify_pair,
)
from alpha_lab.research.local_paper_recovery import main as recovery
from alpha_lab.research.local_paper_terminal import main as terminal
from test_paper_commit_boundaries import ACCOUNT, FixedFeed, NOW, ORDER


class LocalRecoveryTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        source = self.root / "legacy"
        source.mkdir()
        self.journal, self.backup = source / JOURNAL_NAME, self.root / "backup.sqlite3"
        paper = LivePaperSession(source, ACCOUNT, FixedFeed(), clock=lambda: NOW)
        try:
            paper.control("arm", expected_revision=paper.state()["risk"]["revision"])
            paper.order(ORDER)
            self.head = paper.runtime.journal_head
        finally:
            paper.close()
        with closing(sqlite3.connect(self.journal)) as db, db:
            for statement in ("DROP TABLE paper_configuration", "DROP TABLE paper_orders", "DROP TABLE paper_order_history"):
                db.execute(statement)
        shutil.copyfile(self.journal, self.backup)

    def test_read_only_verification_and_legacy_copy_migration_preserve_both_files(self):
        original, backup = self.journal.read_bytes(), self.backup.read_bytes()
        receipt = verify_pair(self.journal, self.backup, minimum_events=1,
                              expected_sequence=1, expected_head=self.head)
        self.assertEqual(receipt["backup_relationship"], "EXACT_FILL_HISTORY")
        self.assertEqual(receipt["independent_fill_checkpoint"], "MATCH")
        self.assertEqual(receipt["journal"]["schema"], "LEGACY")
        self.assertEqual(receipt["journal"]["positions"], {"SOL-USD": "1"})
        target = self.root / "work"
        restored = prepare_working_copy(self.journal, self.backup, target, minimum_events=1)
        self.assertEqual(restored["schema"], "CURRENT")
        self.assertEqual(restored["head"], self.head)
        self.assertEqual(restored["cash_usd"], receipt["journal"]["cash_usd"])
        self.assertEqual(restored["stored_armed_flag"], 0)
        self.assertEqual(self.journal.read_bytes(), original)
        self.assertEqual(self.backup.read_bytes(), backup)
        paper = LivePaperSession(target, ACCOUNT, FixedFeed(), clock=lambda: NOW, migrate=False)
        try:
            self.assertTrue(paper.runtime.ledger.halted)
            self.assertEqual(paper.order(ORDER)["status"], "ALREADY_COMMITTED")
            self.assertEqual(paper.runtime.ledger.sequence, 1)
        finally:
            paper.close()
        with self.assertRaises(FileExistsError):
            prepare_working_copy(self.journal, self.backup, target)

    def test_restore_uses_independent_checkpoint_and_keeps_backup_bytes(self):
        backup = self.backup.read_bytes()
        self.journal.write_bytes(b"corrupted disposable original")
        target = self.root / "restored"
        with self.assertRaisesRegex(ValueError, "independent checkpoint"):
            restore_backup(self.backup, target, expected_sequence=1, expected_head="f" * 64)
        self.assertFalse(target.exists())
        result = restore_backup(self.backup, target, expected_sequence=1, expected_head=self.head)
        self.assertEqual(result["head"], self.head)
        self.assertTrue(result["replay_halted"])
        self.assertEqual(self.backup.read_bytes(), backup)

    def test_stopped_backup_cli_verifies_and_preserves_both_files(self):
        original, backup = self.journal.read_bytes(), self.backup.read_bytes()
        target = self.root / "next.sqlite3"
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(recovery(["backup", "--journal", str(self.journal), "--destination", str(target),
                                       "--minimum-events", "1"]), 0)
        self.assertEqual(json.loads(output.getvalue()), {"status": "PASS", "backup": str(target),
                                                         "events": 1, "backup_relationship": "EXACT_FILL_HISTORY"})
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        with self.assertRaisesRegex(ValueError, "new file"):
            backup_stopped_journal(self.journal, self.backup)
        self.assertEqual(self.journal.read_bytes(), original)
        self.assertEqual(self.backup.read_bytes(), backup)

    def test_backup_failure_removes_only_its_reservation(self):
        original, backup = self.journal.read_bytes(), self.backup.read_bytes()
        target = self.root / "next.sqlite3"
        with patch.object(os, "replace", side_effect=OSError("interrupted publication")):
            with self.assertRaisesRegex(OSError, "interrupted publication"):
                backup_stopped_journal(self.journal, target, minimum_events=1)
        self.assertFalse(target.exists())
        self.assertEqual(self.journal.read_bytes(), original)
        self.assertEqual(self.backup.read_bytes(), backup)

    def test_publication_refuses_destination_created_after_validation(self):
        staged = self.root / "staged.sqlite3"
        shutil.copyfile(self.journal, staged)
        previous = self.backup.read_bytes()
        with self.assertRaises(FileExistsError):
            publish_verified_file(staged, self.backup)
        self.assertEqual(self.backup.read_bytes(), previous)
        self.assertTrue(staged.is_file())

    def test_wrong_path_duplicate_and_rollback_fail_closed(self):
        missing = self.root / "wrong" / JOURNAL_NAME
        with self.assertRaises(FileNotFoundError):
            verify_pair(missing, self.backup)
        self.assertFalse(missing.parent.exists())
        with self.assertRaisesRegex(ValueError, "same file"):
            verify_pair(self.journal, self.journal)
        with closing(sqlite3.connect(self.journal)) as db, db:
            db.execute("DELETE FROM events")
        with self.assertRaisesRegex(ValueError, "sequence disagrees"):
            verify_pair(self.journal, self.backup)

    def test_sidecars_and_active_writer_prevent_copying(self):
        sidecar = self.journal.with_name(JOURNAL_NAME + "-wal")
        sidecar.write_bytes(b"disposable incomplete WAL")
        with self.assertRaisesRegex(ValueError, "sidecar"):
            verify_pair(self.journal, self.backup)
        sidecar.unlink()
        paper = LivePaperSession(self.journal.parent, ACCOUNT, FixedFeed(), clock=lambda: NOW)
        try:
            with self.assertRaisesRegex(ValueError, "active writer"):
                verify_pair(self.journal, self.backup)
        finally:
            paper.close()

    def test_terminal_refuses_missing_directory_or_legacy_schema_without_creating_a_journal(self):
        missing = self.root / "wrong"
        original = self.journal.read_bytes()
        for args, reason in ((["--directory", str(missing)], "working journal missing"),
                             (["--directory", str(self.journal.parent)], "verified working copy"),
                             (["--init", "--directory", str(self.journal.parent)], "File exists")):
            stderr = StringIO()
            with self.subTest(reason=reason), redirect_stderr(stderr), self.assertRaises(SystemExit):
                terminal(args)
            self.assertIn(reason, stderr.getvalue())
        self.assertFalse(missing.exists())
        self.assertEqual(self.journal.read_bytes(), original)

    def test_unknown_sqlite_trigger_is_rejected_even_with_valid_hashes(self):
        with closing(sqlite3.connect(self.journal)) as db, db:
            db.execute("CREATE TRIGGER unexpected AFTER UPDATE ON paper_guard BEGIN SELECT 1; END")
        with self.assertRaisesRegex(ValueError, "executable SQLite schema object"):
            verify_pair(self.journal, self.backup)

    @unittest.skipUnless(hasattr(os, "link"), "platform lacks hard-link support")
    def test_terminal_refuses_an_alias_of_preserved_data(self):
        aliased = self.root / "alias"
        aliased.mkdir()
        os.link(self.journal, aliased / JOURNAL_NAME)
        stderr = StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit):
            terminal(["--directory", str(aliased)])
        self.assertIn("standalone SQLite file", stderr.getvalue())
