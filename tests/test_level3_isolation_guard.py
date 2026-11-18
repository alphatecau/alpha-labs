"""Deployment isolation gate rejects same-UID and incorrectly owned custody."""
import os
import tempfile
import unittest
from pathlib import Path
from tools.level3_staging.isolation_guard import IsolationDenied,verify_isolation

class IsolationTests(unittest.TestCase):
    def test_same_uid_denied(self):
        with self.assertRaises(IsolationDenied):
            verify_isolation(os.getuid(),os.getuid(),"/missing","/missing")
    def test_missing_evidence_denied(self):
        with self.assertRaises(IsolationDenied):
            verify_isolation(os.getuid(),os.getuid()+1,"/missing","/missing")
    def test_same_uid_owned_files_denied(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/"ledger",Path(d)/"audit"
            a.write_text("")
            b.write_text("")
            a.chmod(0o600)
            b.chmod(0o600)
            with self.assertRaises(IsolationDenied):
                verify_isolation(os.getuid(),os.getuid()+1,a,b)

if __name__=="__main__":
    unittest.main()
