"""Independent economic accounting and immutable-evidence checks."""
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from tools.research_evidence_gate import verify, independent_cash_inventory_ledger

class EvidenceGateTests(unittest.TestCase):
    def test_frozen_evidence(self):
        r = verify()
        self.assertEqual(len(r["markets"]), 3)
        self.assertTrue(all(not m["independently_sealed"] for m in r["markets"].values()))
        self.assertTrue(all(Decimal(m["modelled_pnl_usdt"]) < 0 for m in r["markets"].values()))

    def test_tampering_rejected(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "audit.json"
            path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "digest"):
                verify(path)

    def test_roundtrip_fees_and_conservation(self):
        r = independent_cash_inventory_ledger("1000", [("buy", "2", "100"), ("sell", "2", "110")], "110", "10", "10")
        self.assertEqual(r["inventory"], Decimal(0))
        self.assertEqual(r["realised_fees"], Decimal("0.420"))
        self.assertEqual(r["cash"], Decimal("1019.580"))
        self.assertEqual(r["economic_pnl"], Decimal("19.580"))

    def test_open_position_exit_cost_reserved(self):
        r = independent_cash_inventory_ledger("1000", [("buy", "2", "100")], "110", "10", "10")
        self.assertEqual(r["realised_fees"], Decimal("0.200"))
        self.assertEqual(r["estimated_liquidation_nav"], Decimal("1019.360220"))
        self.assertEqual(r["economic_pnl"], Decimal("19.360220"))

    def test_no_leverage_or_shorting(self):
        for initial, fills in [("100", [("buy", "2", "100")]),
                               ("1000", [("sell", "1", "100")])]:
            with self.assertRaises(ValueError):
                independent_cash_inventory_ledger(initial, fills, "100", "10", "10")

if __name__ == "__main__":
    unittest.main()
