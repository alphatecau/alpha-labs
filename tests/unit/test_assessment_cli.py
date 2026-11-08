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

if __name__ == "__main__":
    unittest.main()
