import json
import tempfile
import unittest
from pathlib import Path
from alpha_lab.research.assessment_cli import run_assessment

class AssessmentCliTests(unittest.TestCase):
    def test_no_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run_assessment([], Path(tmp)/"out.json", additional_cost_per_period=0.001)

    def test_unsealed_report_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/"fold.json"
            source.write_text(json.dumps({"schema":"unsupported","trading_enabled":False}))
            output = root/"report.json"
            result = run_assessment([source], output, additional_cost_per_period=0.001)
            self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
            self.assertFalse(result["trading_enabled"])
            self.assertEqual(json.loads(output.read_text())["status"], "INSUFFICIENT_EVIDENCE")
            with self.assertRaises(FileExistsError):
                run_assessment([source], output, additional_cost_per_period=0.001)

    def test_cannot_overwrite_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/"fold.json"
            source.write_text("{}")
            with self.assertRaises(ValueError):
                run_assessment([source], source, additional_cost_per_period=0.001)


    def test_report_contains_input_checksum_and_assumptions(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/"fold.json"
            source.write_text('{"schema":"unsupported","trading_enabled":false}')
            result = run_assessment([source], root/"report.json",
                                    additional_cost_per_period=0.0002,
                                    tested_strategies=4)
            self.assertEqual(result["input_files"][0]["sha256"],
                             hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(result["tested_strategies_declared"], 4)
            self.assertFalse(result["promotion_authorised"])
            self.assertFalse(result["strategy_profitable_verified"])

if __name__ == "__main__":
    unittest.main()
