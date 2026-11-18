"""Interrupted claim must remain blocked after reopening ledger."""
import tempfile
import unittest
from pathlib import Path
from tools.level3_staging.signed_create import _database
from tools.level3_staging.recovery import inspect_claims

class RecoveryInspectionTests(unittest.TestCase):
    def test_missing_ledger_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(inspect_claims(Path(d)/"ledger.db")["blocked"])

    def test_interrupted_claim_stays_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"ledger.db"
            con=_database(path)
            con.execute("INSERT INTO claims(nonce,state) VALUES (?,?)",("a"*64,"claimed"))
            con.close()
            report=inspect_claims(path)
            self.assertTrue(report["blocked"])
            self.assertEqual(report["claims"][0]["state"],"claimed")
            con=_database(path)
            self.assertEqual(con.execute("SELECT state FROM claims").fetchone()[0],"claimed")
            con.close()

    def test_complete_claim_not_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"ledger.db"
            con=_database(path)
            con.execute("INSERT INTO claims(nonce,state) VALUES (?,?)",("b"*64,"complete"))
            con.close()
            self.assertFalse(inspect_claims(path)["blocked"])

if __name__=="__main__":
    unittest.main()
