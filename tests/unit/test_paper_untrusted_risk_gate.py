"""Fail-closed regression tests for the untrusted paper-risk approval boundary."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from alpha_lab.research.paper_runtime import PaperRuntime

class UntrustedRiskAuthorityTests(unittest.TestCase):
    def test_caller_cannot_claim_independent_risk_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime=PaperRuntime(str(Path(directory)/"paper.sqlite3"))
            runtime.enable(operator_approved=True)
            now=datetime.now(timezone.utc)
            with self.assertRaisesRegex(PermissionError,"trusted server-owned risk authority"):
                runtime.execute(symbol="BTC",side="BUY",quantity="0.01",
                    reference_mid="100",executed_price="100",fee="0",
                    quote_timestamp=now,now=now,marks={"BTC":"100"},
                    proposed_loss="0",aggregate_open_risk="0",gross_notional="0",
                    peak_nav="10000",day_start_nav="10000",operator_approved=True,
                    request_id="forged-approval-1",authoritative_risk_verified=True)
            self.assertTrue(runtime.ledger.halted)
            self.assertEqual(runtime.journal.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0],0)
            runtime.close()

if __name__=="__main__":
    unittest.main()
