"""Offline adversarial single-writer protection."""
import tempfile
import unittest
from pathlib import Path
from alpha_lab.research.paper_journal import PaperJournal

class PaperWriterLockTests(unittest.TestCase):
    def test_second_writer_halts_until_first_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "paper.sqlite3")
            first = PaperJournal(path)
            try:
                with self.assertRaisesRegex(PermissionError, "HALT"):
                    PaperJournal(path)
                first.append({"type": "TEST", "value": 1})
            finally:
                first.close()
            second = PaperJournal(path)
            try:
                self.assertEqual(len(list(second.connection.execute("SELECT seq FROM events"))), 1)
                second.verify()
            finally:
                second.close()

if __name__ == "__main__":
    unittest.main()
