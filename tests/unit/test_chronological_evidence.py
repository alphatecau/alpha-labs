import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from alpha_lab.data.csv_import import Bar, Dataset
from alpha_lab.research.chronological_evidence import export_replay_evidence

class ChronologicalEvidenceTests(unittest.TestCase):
    def dataset(self):
        t = datetime(2025, 1, 1, tzinfo=timezone.utc)
        bars = tuple(Bar(t + timedelta(hours=i),
                         Decimal(100 + i % 17), Decimal(101 + i % 17),
                         Decimal(99 + i % 17), Decimal(100 + i % 17), Decimal(100))
                     for i in range(240))
        return Dataset(bars, "USDT", "a" * 64, "synthetic-test", 60)

    def test_timestamped_series_and_ledger_parity(self):
        result = export_replay_evidence(self.dataset(), start=100, end=220,
                                        fold_id="fold-1", code_revision="fixture")
        self.assertEqual(len(result["periods"]), 120)
        self.assertEqual(result["periods"][0]["timestamp_utc"],
                         self.dataset().bars[100].time.isoformat())
        self.assertEqual(result["modelled_order_count"], len(result["orders"]))
        self.assertFalse(result["trading_enabled"])
        self.assertFalse(result["holdout_independently_sealed"])
        self.assertEqual(len(result["evidence_sha256"]), 64)

    def test_reproducible_hash(self):
        a = export_replay_evidence(self.dataset(), start=100, end=220, fold_id="f")
        b = export_replay_evidence(self.dataset(), start=100, end=220, fold_id="f")
        self.assertEqual(a, b)

    def test_invalid_fold_rejected(self):
        with self.assertRaises(ValueError):
            export_replay_evidence(self.dataset(), start=100, end=220, fold_id="")

    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            export_replay_evidence(self.dataset(), start=240, end=250, fold_id="f")

if __name__ == "__main__":
    unittest.main()
