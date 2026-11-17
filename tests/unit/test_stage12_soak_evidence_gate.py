"""Offline validation of Stage 11 soak evidence, including tamper cases."""
import unittest

from alpha_lab.research.stage12_soak_evidence_gate import assess


def valid():
    return {"mode": "READ_ONLY", "status": "PASS", "samples": 120,
            "products": {p: {"healthy": 120, "unverified": 0,
                             "availability_pct": 100.0,
                             "max_exchange_age_seconds": 2.0}
                         for p in ("BTC-USD", "ETH-USD", "SOL-USD")},
            "paper_orders": 0, "live_orders": 0,
            "live_execution_authorised": False}


class Stage12EvidenceGate(unittest.TestCase):
    def test_accepts_consistent_sample_metrics_only(self):
        result = assess(valid())
        self.assertTrue(result["accepted"])
        self.assertIs(result["elapsed_wall_clock_verified"], False)
        self.assertIs(result["production_trading_authorised"], False)

    def test_rejects_short_or_degraded_evidence(self):
        for change in ({"samples": 5}, {"status": "DEGRADED"},
                       {"live_execution_authorised": True},
                       {"paper_orders": 1}, {"live_orders": 1}):
            with self.subTest(change=change):
                report = valid()
                report.update(change)
                self.assertFalse(assess(report)["accepted"])

    def test_rejects_inconsistent_or_stale_product_metrics(self):
        for field, value in (("healthy", 119), ("unverified", 1),
                             ("availability_pct", 98.0),
                             ("max_exchange_age_seconds", 11)):
            with self.subTest(field=field):
                report = valid()
                report["products"]["BTC-USD"][field] = value
                self.assertFalse(assess(report)["accepted"])

    def test_rejects_missing_or_invalid_reports(self):
        self.assertFalse(assess(None)["accepted"])
        report = valid()
        del report["products"]["SOL-USD"]
        self.assertFalse(assess(report)["accepted"])


if __name__ == "__main__":
    unittest.main()
