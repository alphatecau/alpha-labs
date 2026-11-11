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


if __name__ == "__main__":
    unittest.main()
