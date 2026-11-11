import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from alpha_lab.research.paper_runtime import PaperRuntime

class RuntimeTests(unittest.TestCase):
    def test_durable_replay_halt_and_freshness(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/"journal.sqlite3")
            now=datetime(2026,11,9,0,0,tzinfo=timezone.utc)
            r=PaperRuntime(path,starting_cash="1000")
            with self.assertRaises(PermissionError):
                r.execute(symbol="BTC",side="BUY",quantity="1",reference_mid="100",
                    executed_price="100",fee="0",quote_timestamp=now,now=now,
                    marks={},proposed_loss="1",aggregate_open_risk="0",
                    gross_notional="0",peak_nav="1000",day_start_nav="1000",order_id="unapproved-001")
            r.enable(operator_approved=True)
            args=dict(symbol="BTC",side="BUY",quantity="1",reference_mid="100",
                executed_price="100",fee="0",quote_timestamp=now,now=now,
                marks={},proposed_loss="1",aggregate_open_risk="0",
                gross_notional="0",peak_nav="1000",day_start_nav="1000",
                operator_approved=True,order_id="approved-001")
            r.execute(**args)
            self.assertEqual(str(r.ledger.cash),"900")
            r.close()
            restored=PaperRuntime(path,starting_cash="1000")
            self.assertTrue(restored.ledger.halted)
            self.assertEqual(str(restored.ledger.cash),"900")
            self.assertEqual(restored.ledger.sequence,1)
            restored.enable(operator_approved=True)
            args.update(marks={"BTC":"100"},quantity="0.1",now=now+timedelta(minutes=2),order_id="stale-002")
            with self.assertRaisesRegex(PermissionError,"HALT"):
                restored.execute(**args)
            self.assertTrue(restored.ledger.halted)
            self.assertEqual(restored.ledger.sequence,1)
            restored.close()

if __name__=="__main__":
    unittest.main()
