"""Audit durability and corruption detection tests."""
import json
import tempfile
import unittest
from pathlib import Path
from tools.level3_staging.audit_chain import append,verify

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"audit.jsonl"

    def test_chain_and_restart(self):
        first=append(self.path,{"event":"claim","nonce":"a"})
        self.assertEqual(verify(self.path),first)
        second=append(self.path,{"event":"complete","nonce":"a"})
        self.assertEqual(verify(self.path),second)

    def test_mutation_detected(self):
        append(self.path,{"event":"claim"})
        self.path.write_bytes(self.path.read_bytes().replace(b"claim",b"other"))
        with self.assertRaises(ValueError):
            verify(self.path)

    def test_truncated_tail_detected(self):
        append(self.path,{"event":"claim"})
        self.path.write_bytes(self.path.read_bytes()[:-4])
        with self.assertRaises((ValueError,json.JSONDecodeError)):
            verify(self.path)

    def test_symlink_denied(self):
        other=Path(self.tmp.name)/"other"
        other.write_text("")
        self.path.symlink_to(other)
        with self.assertRaises(ValueError):
            append(self.path,{"event":"claim"})

if __name__=="__main__":
    unittest.main()
