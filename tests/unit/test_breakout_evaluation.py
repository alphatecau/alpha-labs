import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from decimal import Decimal
from alpha_lab.research.breakout_evaluation import evaluate_breakout_csv

class BreakoutEvaluationTests(unittest.TestCase):
    def test_offline_report_fail_closed_and_cost_sensitive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/"hourly.csv"
            start = datetime(2025, 1, 1, tzinfo=timezone.utc)
            with source.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(("timestamp","open","high","low","close","volume"))
                for i in range(1200):
                    p = 100+i/10
                    writer.writerow(((start+timedelta(hours=i)).isoformat(),p,p+1,p-1,p,10))
            report = evaluate_breakout_csv(source, root/"result.json",
                                           provenance="synthetic-test-fixture",
                                           start=840, end=1200)
            self.assertFalse(report["trading_enabled"])
            self.assertFalse(report["profitability_verified"])
            self.assertFalse(report["promotion_authorised"])
            self.assertEqual(report["status"], "RESEARCH_ONLY_UNVERIFIED")
            self.assertTrue((root/"result.json").exists())
            with self.assertRaisesRegex(ValueError, "new path"):
                evaluate_breakout_csv(source, root/"result.json",
                                      provenance="synthetic-test-fixture",
                                      start=840, end=1200)
            stressed = evaluate_breakout_csv(source, root/"stressed.json",
                                             provenance="synthetic-test-fixture",
                                             start=840, end=1200,
                                             fee_bps="40", slippage_bps="40")
            self.assertLessEqual(Decimal(stressed["candidate"]["final_liquidatable_value"]),
                                 Decimal(report["candidate"]["final_liquidatable_value"]))

    def test_rejects_unlabelled_source(self):
        with self.assertRaisesRegex(ValueError, "provenance"):
            evaluate_breakout_csv("missing.csv", "output.json",
                                  provenance="", start=840, end=1200)

if __name__ == "__main__":
    unittest.main()
