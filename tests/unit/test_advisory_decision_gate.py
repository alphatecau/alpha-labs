"""No-trade gate cannot be used to authorise simulated or live execution."""
import unittest
from datetime import datetime, timezone
from alpha_lab.research.advisory_decision_gate import advisory_decision

NOW = datetime(2026, 11, 17, tzinfo=timezone.utc)


def fixture():
    return dict(status="RESEARCH_ONLY_NOT_VALIDATED_ALPHA",
                product_id="BTC-USD", granularity=14400,
                source_sha256="a" * 64, candle_count=60,
                trend_observation="UPTREND_OBSERVED", decision="FLAT",
                risk_override="HALT", paper_execution_authorised=False,
                live_execution_authorised=False)


class AdvisoryDecisionGateTests(unittest.TestCase):
    def assert_halted(self, result):
        self.assertEqual(result["risk_override"], "HALT")
        self.assertIs(result["paper_execution_authorised"], False)
        self.assertIs(result["live_execution_authorised"], False)

    def test_valid_descriptive_trend_never_authorises_execution(self):
        for trend in ("UPTREND_OBSERVED", "DOWNTREND_OBSERVED", "MIXED"):
            with self.subTest(trend=trend):
                report = fixture()
                report["trend_observation"] = trend
                result = advisory_decision(report, now=NOW)
                self.assertEqual(result["decision"], "NO_TRADE")
                self.assert_halted(result)

    def test_missing_or_malformed_evidence_fails_closed(self):
        for field, value in (
            ("status", "APPROVED"), ("decision", "LONG"),
            ("risk_override", "ARMED"), ("paper_execution_authorised", True),
            ("live_execution_authorised", True), ("candle_count", 59),
            ("candle_count", True), ("granularity", 0),
            ("source_sha256", "invalid"), ("product_id", "UNKNOWN"),
            ("trend_observation", "BUY")):
            with self.subTest(field=field):
                report = fixture()
                report[field] = value
                result = advisory_decision(report, now=NOW)
                self.assertEqual(result["decision"], "UNVERIFIED")
                self.assert_halted(result)
        self.assertEqual(advisory_decision(None, now=NOW)["decision"], "UNVERIFIED")
        report = fixture()
        del report["source_sha256"]
        self.assertEqual(advisory_decision(report, now=NOW)["decision"], "UNVERIFIED")

    def test_unhashable_evidence_fails_closed(self):
        for field in ("product_id", "trend_observation"):
            for value in ([], {}, set()):
                with self.subTest(field=field, value_type=type(value).__name__):
                    report = fixture()
                    report[field] = value
                    result = advisory_decision(report, now=NOW)
                    self.assertEqual(result["decision"], "UNVERIFIED")
                    self.assert_halted(result)

    def test_invalid_clock_type_is_rejected(self):
        with self.assertRaises(ValueError):
            advisory_decision(fixture(), now="2026-11-17T00:00:00Z")

    def test_timestamp_requires_timezone(self):
        with self.assertRaises(ValueError):
            advisory_decision(fixture(), now=datetime(2026, 11, 17))


if __name__ == "__main__":
    unittest.main()
