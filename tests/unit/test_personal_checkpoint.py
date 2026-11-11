"""Adversarial authenticated checkpoint tests; key is separate from journal."""
import json
import tempfile
import unittest
from pathlib import Path

from alpha_lab.research.paper_journal import PaperJournal
from alpha_lab.research.paper_checkpoint import seal_checkpoint, verify_sealed_checkpoint


class PersonalCheckpointTests(unittest.TestCase):
    def test_valid_checkpoint_and_tail_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = PaperJournal(str(Path(tmp) / "journal.sqlite"))
            try:
                journal.append({"type": "FILL", "simulated": True, "index": 1})
                journal.append({"type": "FILL", "simulated": True, "index": 2})
                key = b"k" * 32
                envelope = seal_checkpoint(sequence=2, head=journal.verify(), secret=key)
                self.assertEqual(verify_sealed_checkpoint(journal, envelope, secret=key),
                                 journal.verify())
                journal.connection.execute("DELETE FROM events WHERE seq=2")
                journal.connection.commit()
                with self.assertRaisesRegex(ValueError, "journal checkpoint mismatch"):
                    verify_sealed_checkpoint(journal, envelope, secret=key)
            finally:
                journal.close()

    def test_modified_envelope_wrong_key_and_short_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = PaperJournal(str(Path(tmp) / "journal.sqlite"))
            try:
                envelope = seal_checkpoint(sequence=0, head=journal.verify(), secret=b"a" * 32)
                forged = json.loads(envelope)
                forged["sequence"] = 1
                with self.assertRaisesRegex(ValueError, "authentication failure"):
                    verify_sealed_checkpoint(journal, json.dumps(forged), secret=b"a" * 32)
                with self.assertRaisesRegex(ValueError, "authentication failure"):
                    verify_sealed_checkpoint(journal, envelope, secret=b"b" * 32)
                with self.assertRaisesRegex(ValueError, "at least 32 bytes"):
                    seal_checkpoint(sequence=0, head=journal.verify(), secret=b"weak")
            finally:
                journal.close()

    def test_old_legitimate_checkpoint_requires_external_monotonic_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = PaperJournal(str(Path(tmp) / "journal.sqlite"))
            try:
                key = b"z" * 32
                old = seal_checkpoint(sequence=0, head=journal.verify(), secret=key)
                journal.append({"type": "FILL", "simulated": True})
                journal.connection.execute("DELETE FROM events WHERE seq=1")
                journal.connection.commit()
                # Demonstrates a remaining limitation, not a security guarantee.
                self.assertEqual(verify_sealed_checkpoint(journal, old, secret=key),
                                 "0" * 64)
            finally:
                journal.close()


if __name__ == "__main__":
    unittest.main()
