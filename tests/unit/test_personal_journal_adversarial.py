"""Adversarial journal verification for the Personal Edition offline paper engine."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from alpha_lab.research.paper_journal import PaperJournal


class PersonalJournalAdversarialTests(unittest.TestCase):
    def test_payload_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "events.sqlite3")
            journal = PaperJournal(path)
            journal.append({"type": "FILL", "simulated": True, "symbol": "BTC"})
            journal.close()
            connection = sqlite3.connect(path)
            connection.execute("UPDATE events SET payload=? WHERE seq=1",
                               ('{"type":"FILL","simulated":false,"symbol":"BTC"}',))
            connection.commit()
            connection.close()
            reopened = PaperJournal(path)
            try:
                with self.assertRaisesRegex(ValueError, "journal integrity failure"):
                    reopened.verify()
            finally:
                reopened.close()

    def test_previous_hash_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "events.sqlite3")
            journal = PaperJournal(path)
            journal.append({"type": "FILL", "simulated": True})
            journal.append({"type": "FILL", "simulated": True})
            journal.connection.execute("UPDATE events SET previous_hash=? WHERE seq=2",
                                       ("f" * 64,))
            journal.connection.commit()
            with self.assertRaisesRegex(ValueError, "journal integrity failure"):
                journal.verify()
            journal.close()


    def test_deleted_middle_event_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "events.sqlite3")
            journal = PaperJournal(path)
            for i in range(3):
                journal.append({"type": "FILL", "simulated": True, "index": i})
            journal.connection.execute("DELETE FROM events WHERE seq=2")
            journal.connection.commit()
            with self.assertRaisesRegex(ValueError, "journal sequence gap"):
                journal.verify()
            journal.close()

    def test_trailing_event_deletion_requires_external_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "events.sqlite3")
            journal = PaperJournal(path)
            journal.append({"type": "FILL", "simulated": True, "index": 1})
            journal.append({"type": "FILL", "simulated": True, "index": 2})
            trusted_head = journal.verify()
            journal.connection.execute("DELETE FROM events WHERE seq=2")
            journal.connection.commit()
            self.assertNotEqual(journal.verify(), trusted_head)
            journal.close()

if __name__ == "__main__":
    unittest.main()
