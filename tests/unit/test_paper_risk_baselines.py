import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from alpha_lab.research.paper_risk_baselines import RiskBaselineJournal

class BaselineTests(unittest.TestCase):
    def test_restart_rollover_peak_and_day_start(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/"risk.db")
            first=datetime(2026,11,9,12,tzinfo=timezone.utc)
            j=RiskBaselineJournal(path)
            head,a=j.record(now=first,nav="1000")
            head,b=j.record(now=first+timedelta(hours=1),nav="950",expected_head=head)
            self.assertEqual(b["day_start_nav"],"1000")
            self.assertEqual(b["peak_nav"],"1000")
            j.close()
            j=RiskBaselineJournal(path)
            head,c=j.record(now=first+timedelta(days=1),nav="970")
            self.assertEqual(c["day_start_nav"],"950")
            self.assertEqual(c["peak_nav"],"1000")
            j.close()
    def test_tamper_and_concurrent_writer_denied(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/"risk.db")
            now=datetime(2026,11,9,tzinfo=timezone.utc)
            a=RiskBaselineJournal(path)
            b=RiskBaselineJournal(path)
            zero="0"*64
            a.record(now=now,nav="1000",expected_head=zero)
            with self.assertRaisesRegex(ValueError,"HALT"):
                b.record(now=now,nav="999",expected_head=zero)
            a.db.execute("UPDATE risk_baselines SET payload='{}' WHERE seq=1")
            a.db.commit()
            with self.assertRaisesRegex(ValueError,"HALT"):
                b.verify()
            a.close()
            b.close()
    def test_invalid_clock_and_nav_denied(self):
        with tempfile.TemporaryDirectory() as d:
            j=RiskBaselineJournal(str(Path(d)/"risk.db"))
            with self.assertRaisesRegex(ValueError,"HALT"):
                j.record(now=datetime(2026,11,9),nav="1000")
            with self.assertRaisesRegex(ValueError,"HALT"):
                j.record(now=datetime(2026,11,9,tzinfo=timezone.utc),nav="NaN")
            j.close()
if __name__=="__main__":
    unittest.main()
