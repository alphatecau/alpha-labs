"""Crash-state and fail-closed tests for the experimental Level 3 approval ledger."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from tools.level3_staging.approval_ledger import ApprovalDenied, issue, claim, complete

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'approvals.db'
        self.secret = b'test-key-not-for-deployment'
        self.path = 'docs/level3-staging/recovery.md'
        self.digest = 'a' * 64
        self.nonce = 'r' * 32
        issue(self.db, self.secret, self.path, self.digest, 1100, self.nonce)

    def test_claimed_after_restart_cannot_replay(self):
        claim(self.db, self.secret, self.path, self.digest, self.nonce, now=1000)
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('SELECT state FROM approvals').fetchone()[0], 'claimed')
        with self.assertRaises(ApprovalDenied):
            claim(self.db, self.secret, self.path, self.digest, self.nonce, now=1000)

    def test_completed_after_restart_cannot_replay(self):
        claim(self.db, self.secret, self.path, self.digest, self.nonce, now=1000)
        complete(self.db, self.nonce)
        with self.assertRaises(ApprovalDenied):
            claim(self.db, self.secret, self.path, self.digest, self.nonce, now=1000)

    def test_unclaimed_cannot_be_completed(self):
        with self.assertRaises(ApprovalDenied):
            complete(self.db, self.nonce)

    def test_tampered_claim_state_denied(self):
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE approvals SET state='claimed'")
        with self.assertRaises(ApprovalDenied):
            claim(self.db, self.secret, self.path, self.digest, self.nonce, now=1000)

if __name__ == '__main__':
    unittest.main()
