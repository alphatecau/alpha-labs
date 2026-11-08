import tempfile
import unittest
from pathlib import Path
from alpha_lab.research.paper_risk import authorise_simulated_order
from alpha_lab.research.paper_journal import PaperJournal

class PaperSafetyTests(unittest.TestCase):
    def test_default_fail_closed(self):
        decision = authorise_simulated_order(nav=1000,initial_nav=1000,peak_nav=1000,
            day_start_nav=1000,proposed_loss=1,aggregate_open_risk=0,
            gross_notional=0,proposed_notional=100,data_fresh=False,
            ledger_reconciled=False,operator_enabled=False)
        self.assertFalse(decision["approved"])
        self.assertFalse(decision["live_execution_authorised"])

    def test_risk_budget(self):
        base=dict(nav=1000,initial_nav=1000,peak_nav=1000,day_start_nav=1000,
            proposed_loss=3,aggregate_open_risk=0,gross_notional=0,
            proposed_notional=100,data_fresh=True,ledger_reconciled=True,operator_enabled=True)
        self.assertFalse(authorise_simulated_order(**base)["approved"])
        base["proposed_loss"]=2
        self.assertTrue(authorise_simulated_order(**base)["approved"])

    def test_journal_reopen_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/"paper.sqlite3")
            j=PaperJournal(path)
            digest=j.append({"type":"SIMULATED_FILL","quantity":"1"})
            self.assertEqual(j.verify(),digest)
            j.close()
            j=PaperJournal(path)
            self.assertEqual(j.verify(),digest)
            j.connection.execute("UPDATE events SET payload='{}' WHERE seq=1")
            j.connection.commit()
            with self.assertRaisesRegex(ValueError,"HALT"):
                j.verify()
            j.close()

if __name__=="__main__":
    unittest.main()
