import unittest

from tools.level3_staging.custody_release_gate import (
    REQUIRED_GATES,
    evaluate_release,
)


class ReleaseGateTests(unittest.TestCase):
    def test_missing_evidence_denied(self):
        result = evaluate_release({})
        self.assertFalse(result["allowed"])
        self.assertEqual(set(result["missing"]), REQUIRED_GATES)

    def test_boolean_false_denied(self):
        evidence = dict.fromkeys(REQUIRED_GATES, True)
        evidence["auditor_oauth_scopes"] = False
        self.assertIn("auditor_oauth_scopes", evaluate_release(evidence)["missing"])

    def test_truthy_string_denied(self):
        evidence = dict.fromkeys(REQUIRED_GATES, True)
        evidence["security_review"] = "passed"
        self.assertFalse(evaluate_release(evidence)["allowed"])

    def test_all_asserted_true(self):
        evidence = dict.fromkeys(REQUIRED_GATES, True)
        self.assertTrue(evaluate_release(evidence)["allowed"])

    def test_invalid_evidence_denied(self):
        self.assertFalse(evaluate_release(None)["allowed"])
