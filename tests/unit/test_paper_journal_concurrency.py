import tempfile
import unittest
from pathlib import Path
from alpha_lab.research.paper_journal import PaperJournal

class JournalConcurrencyTests(unittest.TestCase):
    def test_two_connections_cannot_commit_stale_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/"events.sqlite3")
            a=PaperJournal(path)
            b=PaperJournal(path)
            zero="0"*64
            first=a.append({"type":"TEST","seq":1},expected_previous_hash=zero)
            with self.assertRaisesRegex(ValueError,"concurrent journal modification"):
                b.append({"type":"TEST","seq":2},expected_previous_hash=zero)
            self.assertEqual(b.verify(),first)
            self.assertEqual(a.verify(),first)
            a.close()
            b.close()
    def test_corrupted_event_blocks_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/"events.sqlite3")
            a=PaperJournal(path)
            a.append({"type":"TEST"},expected_previous_hash="0"*64)
            a.connection.execute("UPDATE events SET payload='{}' WHERE seq=1")
            a.connection.commit()
            with self.assertRaisesRegex(ValueError,"HALT"):
                a.append({"type":"NEXT"})
            a.close()
if __name__=="__main__":
    unittest.main()
