import importlib.util
import pathlib
import unittest

PATH = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "engineering_status.py"
SPEC = importlib.util.spec_from_file_location("engineering_status", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class EngineeringStatusTests(unittest.TestCase):
    def test_correlates_checks_by_exact_commit(self):
        prs = [{"number": 91, "title": "Team", "draft": True, "html_url": "https://example/pr/91", "head": {"sha": "abc"}}]
        runs = {"workflow_runs": [
            {"head_sha": "abc", "name": "unit", "status": "completed", "conclusion": "success", "html_url": "https://example/run/1"},
            {"head_sha": "other", "name": "unit", "status": "completed", "conclusion": "failure", "html_url": "https://example/run/2"},
        ]}
        result = MODULE.summarise(prs, runs)
        self.assertEqual(len(result["open_prs"][0]["recent_checks"]), 1)
        self.assertEqual(result["open_prs"][0]["recent_checks"][0]["conclusion"], "success")

    def test_missing_checks_are_not_inferred_as_passed(self):
        prs = [{"number": 92, "title": "No runs", "draft": True, "html_url": "https://example/pr/92", "head": {"sha": "xyz"}}]
        result = MODULE.summarise(prs, {"workflow_runs": []})
        self.assertEqual(result["open_prs"][0]["recent_checks"], [])
        self.assertIn("not proof of passing", result["note"])

if __name__ == "__main__":
    unittest.main()
