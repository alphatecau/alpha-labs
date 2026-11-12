"""Assessment CLI boundary tests: forged quantitative evidence cannot promote.

No profitability, NAV or sealed holdout claim is made by these tests.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alpha_lab.research.assessment_cli import run_assessment


class AssessmentBoundaryTests(unittest.TestCase):
    def test_forged_positive_assessment_remains_research_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "fold.json"
            source.write_text(json.dumps({
                "schema": "forged", "promotion_authorised": True,
                "live_trading_authorised": True,
                "source_price_independently_authenticated": True,
                "historical_capture_independently_attested": True,
            }), encoding="utf-8")
            forged = {
                "status": "PASS",
                "reasons": [],
                "promotion_authorised": True,
                "live_trading_authorised": True,
                "strategy_profitable_verified": True,
            }
            with patch(
                "alpha_lab.research.assessment_cli.assess_evidence",
                return_value=forged,
            ):
                report = run_assessment(
                    [source], root / "assessment.json",
                    additional_cost_per_period=0.001,
                )
            self.assertIs(report["promotion_authorised"], False)
            self.assertIs(report["live_trading_authorised"], False)
            self.assertIs(report["strategy_profitable_verified"], False)
            self.assertIs(report["source_price_independently_authenticated"], False)
            self.assertIs(report["archive_provenance_independently_authenticated"], False)
            self.assertIs(report["historical_capture_independently_attested"], False)
            self.assertEqual(
                json.loads((root / "assessment.json").read_text())["promotion_authorised"],
                False,
            )


if __name__ == "__main__":
    unittest.main()
