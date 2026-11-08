import copy
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from alpha_lab.data.csv_import import Bar, Dataset
from alpha_lab.research.chronological_evidence import export_replay_evidence
from alpha_lab.research.accounting_reconciliation import reconcile_evidence

class AccountingReconciliationTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        bars = tuple(Bar(start + timedelta(hours=i), Decimal(100+i%17),
                         Decimal(101+i%17), Decimal(99+i%17),
                         Decimal(100+i%17), Decimal(100)) for i in range(300))
        self.dataset = Dataset(bars, "USDT", "a"*64, "synthetic", 60)
        self.evidence = export_replay_evidence(self.dataset, start=100, end=260, fold_id="fold-1")

    def test_independent_period_reconciliation(self):
        result = reconcile_evidence(self.dataset, self.evidence)
        self.assertEqual(result["status"], "MODELLED_ACCOUNTING_RECONCILED")
        self.assertEqual(result["periods_reconciled"], 160)
        self.assertFalse(result["trading_enabled"])

    def test_detects_tampered_nav(self):
        doc = copy.deepcopy(self.evidence)
        doc["periods"][17]["net_modelled_nav"] = "9999"
        with self.assertRaisesRegex(ValueError, "Period NAV mismatch"):
            reconcile_evidence(self.dataset, doc)

    def test_detects_tampered_return(self):
        doc = copy.deepcopy(self.evidence)
        doc["periods"][17]["net_period_return"] = 0.1234
        with self.assertRaisesRegex(ValueError, "Period return mismatch"):
            reconcile_evidence(self.dataset, doc)

    def test_rejects_different_source(self):
        doc = copy.deepcopy(self.evidence)
        doc["dataset_sha256"] = "b"*64
        with self.assertRaisesRegex(ValueError, "Dataset checksum mismatch"):
            reconcile_evidence(self.dataset, doc)


    def test_detects_tampered_order_ledger(self):
        doc = copy.deepcopy(self.evidence)
        if not doc["orders"]:
            self.skipTest("Fixture generated no orders")
        doc["orders"][0]["quantity"] = "999"
        with self.assertRaisesRegex(ValueError, "Order ledger mismatch"):
            reconcile_evidence(self.dataset, doc)

    def test_detects_tampered_order_count(self):
        doc = copy.deepcopy(self.evidence)
        doc["modelled_order_count"] += 1
        with self.assertRaisesRegex(ValueError, "Order count mismatch"):
            reconcile_evidence(self.dataset, doc)


    def test_zero_trade_flat_market(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        bars = tuple(Bar(start + timedelta(hours=i), Decimal("100"),
                         Decimal("101"), Decimal("99"), Decimal("100"),
                         Decimal("10")) for i in range(200))
        dataset = Dataset(bars, "USDT", "f"*64, "synthetic-flat", 60)
        evidence = export_replay_evidence(dataset, start=80, end=180, fold_id="flat")
        result = reconcile_evidence(dataset, evidence)
        self.assertEqual(result["modelled_order_count"], 0)
        self.assertEqual(result["closed_trades"], 0)
        self.assertEqual(result["max_drawdown_pct"], 0.0)

    def test_cost_sensitivity_and_open_position(self):
        from alpha_lab.backtest.costs import CostModel
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        bars = tuple(Bar(start + timedelta(hours=i), Decimal(100+i),
                         Decimal(101+i), Decimal(99+i), Decimal(100+i),
                         Decimal(10)) for i in range(200))
        dataset = Dataset(bars, "USDT", "e"*64, "synthetic-trend", 60)
        for fee, slippage in ((0, 0), (10, 10), (35, 75)):
            with self.subTest(fee=fee, slippage=slippage):
                costs = CostModel(Decimal(fee), Decimal(slippage))
                evidence = export_replay_evidence(dataset, start=80, end=180,
                                                  fold_id="trend", costs=costs)
                result = reconcile_evidence(dataset, evidence)
                self.assertEqual(result["modelled_order_count"], len(evidence["orders"]))
                self.assertGreaterEqual(result["max_drawdown_pct"], 0)
                self.assertEqual(result["closed_trades"], evidence["closed_trades"])

if __name__ == "__main__":
    unittest.main()
