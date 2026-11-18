"""Readiness gate must deny activation by default."""
import unittest
from tools.level3_staging.readiness import Gate

class ReadinessTests(unittest.TestCase):
    def test_default_denied(self):
        self.assertFalse(Gate().may_activate())
        self.assertEqual(len(Gate().blockers()),8)

    def test_partial_gate_denied(self):
        self.assertFalse(Gate(ci_green=True, isolated_uid=True).may_activate())

    def test_full_evidence_allows_activation(self):
        self.assertTrue(Gate(True,True,True,True,True,True,True,True).may_activate())

if __name__ == "__main__":
    unittest.main()
