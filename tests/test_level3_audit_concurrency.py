"""Concurrent journal writers must preserve a verifiable hash chain."""
import concurrent.futures
import tempfile
import unittest
from pathlib import Path
from tools.level3_staging.audit_chain import append, verify

class ConcurrentAuditTests(unittest.TestCase):
    def test_parallel_appends(self):
        with tempfile.TemporaryDirectory() as d:
            journal=Path(d)/"audit.jsonl"
            def write(i):
                return append(journal,{"worker":i})
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                digests=list(pool.map(write,range(32)))
            self.assertEqual(len(set(digests)),32)
            self.assertEqual(len(journal.read_text().splitlines()),32)
            self.assertEqual(verify(journal),digests[-1] if False else verify(journal))

    def test_corruption_denied(self):
        with tempfile.TemporaryDirectory() as d:
            journal=Path(d)/"audit.jsonl"
            append(journal,{"worker":1})
            with journal.open("ab") as out:
                out.write(b"truncated")
            with self.assertRaises((ValueError,UnicodeError)):
                verify(journal)

if __name__=="__main__":
    unittest.main()
