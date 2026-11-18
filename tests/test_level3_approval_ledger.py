"""Offline tests of experimental Level 3 approval ledger."""
import concurrent.futures
import sqlite3
import tempfile
import unittest
from pathlib import Path
from tools.level3_staging.approval_ledger import ApprovalDenied, issue, claim, complete

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/'approvals.db'
        self.secret=b'operator-only-test-key'
        self.path='docs/level3-staging/a.md'
        self.digest='a'*64
        self.nonce='n'*32
        issue(self.db,self.secret,self.path,self.digest,1100,self.nonce)

    def test_claim_complete(self):
        claim(self.db,self.secret,self.path,self.digest,self.nonce,1000)
        complete(self.db,self.nonce)
        with self.assertRaises(ApprovalDenied):
            claim(self.db,self.secret,self.path,self.digest,self.nonce,1000)

    def test_replay(self):
        claim(self.db,self.secret,self.path,self.digest,self.nonce,1000)
        with self.assertRaises(ApprovalDenied):
            claim(self.db,self.secret,self.path,self.digest,self.nonce,1000)

    def test_expired(self):
        with self.assertRaises(ApprovalDenied):
            claim(self.db,self.secret,self.path,self.digest,self.nonce,1100)

    def test_wrong_path(self):
        with self.assertRaises(ApprovalDenied):
            claim(self.db,self.secret,'docs/level3-staging/b.md',self.digest,self.nonce,1000)

    def test_wrong_digest(self):
        with self.assertRaises(ApprovalDenied):
            claim(self.db,self.secret,self.path,'b'*64,self.nonce,1000)

    def test_wrong_secret(self):
        with self.assertRaises(ApprovalDenied):
            claim(self.db,b'wrong',self.path,self.digest,self.nonce,1000)

    def test_tampered_signature(self):
        with sqlite3.connect(self.db) as con:
            con.execute('UPDATE approvals SET signature=?',('0'*64,))
        with self.assertRaises(ApprovalDenied):
            claim(self.db,self.secret,self.path,self.digest,self.nonce,1000)

    def test_concurrent(self):
        def worker(_):
            try:
                claim(self.db,self.secret,self.path,self.digest,self.nonce,1000)
                return True
            except ApprovalDenied:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(worker,range(8)))
        self.assertEqual(results.count(True),1)

    def test_claim_persists_after_reopen(self):
        claim(self.db,self.secret,self.path,self.digest,self.nonce,1000)
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('SELECT state FROM approvals').fetchone()[0],'claimed')

    def test_duplicate_nonce(self):
        with self.assertRaises(sqlite3.IntegrityError):
            issue(self.db,self.secret,self.path,self.digest,1100,self.nonce)

if __name__=='__main__':
    unittest.main()
