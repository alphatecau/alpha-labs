import copy
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from alpha_lab.data.csv_import import Bar, Dataset
from alpha_lab.research.chronological_evidence import export_replay_evidence
from alpha_lab.research.evidence_assessment import assess_evidence

class EvidenceAssessmentTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        bars = tuple(Bar(start + timedelta(hours=i), Decimal(100+i%17),
                         Decimal(101+i%17), Decimal(99+i%17),
                         Decimal(100+i%17), Decimal(100)) for i in range(400))
        self.dataset = Dataset(bars, "USDT", "a"*64, "synthetic", 60)
        self.first = export_replay_evidence(self.dataset, start=100, end=240, fold_id="one")
        self.second = export_replay_evidence(self.dataset, start=240, end=380, fold_id="two")

    def test_unsealed_evidence_never_promoted(self):
        result = assess_evidence([self.first, self.second], additional_cost_per_period=0.0001)
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(result["trading_enabled"])
        self.assertEqual(result["observation_count"], 280)
        self.assertIn("HOLDOUT_NOT_INDEPENDENTLY_SEALED", result["reasons"])

    def test_tampered_nav_rejected(self):
        corrupted = copy.deepcopy(self.first)
        corrupted["periods"][0]["net_modelled_nav"] = "999999"
        result = assess_evidence([corrupted], additional_cost_per_period=0.0001)
        self.assertTrue(any("EVIDENCE_CHECKSUM_MISMATCH" in x for x in result["reasons"]))

    def test_overlap_rejected(self):
        result = assess_evidence([self.first, self.first], additional_cost_per_period=0.0001)
        self.assertTrue(any("OVERLAPPING" in x for x in result["reasons"]))

    def test_missing_data_rejected(self):
        result = assess_evidence([], additional_cost_per_period=0.0001)
        self.assertIn("NO_EVIDENCE", result["reasons"])

    def test_invalid_cost_rejected(self):
        result = assess_evidence([self.first], additional_cost_per_period=-0.01)
        self.assertTrue(any("INVALID_COST_STRESS" in x for x in result["reasons"]))

if __name__ == "__main__":
    unittest.main()
