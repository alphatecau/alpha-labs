"""Offline crash-boundary and tamper tests for Level 3 intent reconciliation."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from tools.level3_staging.intent_recovery import reconcile_intent,RecoveryConflict

class IntentRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/"docs/level3-staging").mkdir(parents=True)
        self.path="docs/level3-staging/test.md"
        self.data=b"durable intent"
        self.digest=hashlib.sha256(self.data).hexdigest()
        self.nonce="a"*64
    def run_reconcile(self,payload=None,fault=None):
        return reconcile_intent(self.root,self.nonce,self.path,self.digest,payload,fault)
    def test_create_and_idempotent_replay(self):
        self.assertEqual(self.run_reconcile(self.data),"ready")
        self.assertEqual(self.run_reconcile(),"ready")
    def test_crash_before_write_then_recover(self):
        with self.assertRaises(RuntimeError):
            self.run_reconcile(self.data,"before_write")
        self.assertEqual(self.run_reconcile(self.data),"ready")
    def test_crash_after_temp_then_recover(self):
        with self.assertRaises(RuntimeError):
            self.run_reconcile(self.data,"after_temp")
        self.assertEqual(self.run_reconcile(self.data),"ready")
    def test_crash_after_link_then_recover_without_payload(self):
        with self.assertRaises(RuntimeError):
            self.run_reconcile(self.data,"after_link")
        self.assertEqual(self.run_reconcile(),"ready")
    def test_missing_payload_fails_closed(self):
        with self.assertRaises(RecoveryConflict):
            self.run_reconcile()
    def test_tampered_file_fails_closed(self):
        self.run_reconcile(self.data)
        (self.root/self.path).write_bytes(b"tampered")
        with self.assertRaises(RecoveryConflict):
            self.run_reconcile(self.data)
    def test_symlink_denied(self):
        (self.root/self.path).symlink_to(self.root/"elsewhere")
        with self.assertRaises(RecoveryConflict):
            self.run_reconcile(self.data)

if __name__=="__main__":
    unittest.main()
