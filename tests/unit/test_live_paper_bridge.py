"""Offline persistent paper-order bridge regression."""
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from alpha_lab.research.paper_runtime import PaperRuntime
from alpha_lab.research.live_paper_quotes import parse_book_ticker
from alpha_lab.research.live_paper_bridge import LivePaperBridge

NOW = datetime(2026,11,12,tzinfo=timezone.utc)

class LivePaperBridgeTests(unittest.TestCase):
    def test_persistent_idempotency_and_halt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/"paper.sqlite3")
            quote=parse_book_ticker({"symbol":"BTCUSDT","bidPrice":"99","askPrice":"100"},
                                    symbol="BTCUSDT",observed_at=NOW)
            args=dict(order_id="order-001",quote=quote,side="BUY",quantity="1",
                      now=NOW,marks={},proposed_loss="1",aggregate_open_risk="0",
                      gross_notional="0",peak_nav="1000",day_start_nav="1000",
                      operator_approved=True)
            runtime=PaperRuntime(path,starting_cash="1000")
            runtime.enable(operator_approved=True)
            bridge=LivePaperBridge(runtime)
            first=bridge.submit(**args)
            self.assertEqual(first["status"],"SIMULATED_FILL")
            self.assertEqual(bridge.submit(**args)["status"],"ALREADY_COMMITTED")
            self.assertEqual(runtime.ledger.sequence,1)
            runtime.close()
            restored=PaperRuntime(path,starting_cash="1000")
            restored.enable(operator_approved=True)
            self.assertEqual(LivePaperBridge(restored).submit(**args)["status"],"ALREADY_COMMITTED")
            with self.assertRaises(ValueError):
                LivePaperBridge(restored).submit(**dict(args,quantity="2"))
            stale=dict(args,order_id="order-002",now=NOW+timedelta(seconds=20),
                       marks={"BTCUSDT":"100"})
            with self.assertRaisesRegex(PermissionError,"HALT"):
                LivePaperBridge(restored).submit(**stale)
            self.assertTrue(restored.ledger.halted)
            self.assertEqual(restored.ledger.sequence,1)
            restored.close()

if __name__=="__main__":
    unittest.main()
