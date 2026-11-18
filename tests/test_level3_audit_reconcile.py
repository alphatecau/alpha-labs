"""Reconciliation blocks missing and fabricated journal evidence."""
import tempfile
import unittest
from pathlib import Path
from tools.level3_staging.audit_chain import append
from tools.level3_staging.audit_reconcile import inspect_outbox
from tools.level3_staging.signed_create import _database

class AuditReconcileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/"ledger.db"
        self.audit=Path(self.tmp.name)/"audit.jsonl"
        con=_database(self.db)
        con.execute("INSERT INTO audit_outbox(nonce,phase,path,sha256) VALUES (?,?,?,?)",
                    ("a"*64,"claimed","docs/level3-staging/a.md","b"*64))
        con.close()
        self.event={"nonce":"a"*64,"phase":"claimed","path":"docs/level3-staging/a.md","sha256":"b"*64}

    def test_missing_audit_denied(self):
        self.assertTrue(inspect_outbox(self.db,self.audit)["blocked"])

    def test_undelivered_claim_denied(self):
        self.audit.write_text("")
        self.assertEqual(inspect_outbox(self.db,self.audit)["pending_count"],1)

    def test_matching_evidence(self):
        append(self.audit,self.event)
        self.assertFalse(inspect_outbox(self.db,self.audit)["blocked"])

    def test_duplicate_denied(self):
        append(self.audit,self.event)
        append(self.audit,self.event)
        self.assertTrue(inspect_outbox(self.db,self.audit)["blocked"])

    def test_unknown_event_denied(self):
        append(self.audit,{**self.event,"nonce":"c"*64})
        self.assertTrue(inspect_outbox(self.db,self.audit)["blocked"])

if __name__=="__main__":
    unittest.main()
