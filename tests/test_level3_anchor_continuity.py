"""Offline checks for independent audit checkpoint continuity."""
import unittest
from tools.level3_staging.anchor_continuity import verify_continuity,AnchorContinuityDenied

def receipt(count,sequence,head="a"*64,audience="alpha-labs-level3:staging"):
    return {"version":1,"audience":audience,"count":count,
            "last_sequence":sequence,"head_hash":head}

class ContinuityTests(unittest.TestCase):
    def test_unchanged_checkpoint(self):
        self.assertEqual(verify_continuity(receipt(2,2),receipt(2,2)),"unchanged")
    def test_rollback_denied(self):
        with self.assertRaises(AnchorContinuityDenied):
            verify_continuity(receipt(3,3),receipt(2,2))
    def test_same_height_equivocation_denied(self):
        with self.assertRaises(AnchorContinuityDenied):
            verify_continuity(receipt(2,2),receipt(2,2,"b"*64))
    def test_audience_change_denied(self):
        with self.assertRaises(AnchorContinuityDenied):
            verify_continuity(receipt(2,2),receipt(3,3,audience="other"))
    def test_growth_requires_chain_proof(self):
        self.assertEqual(verify_continuity(receipt(2,2),receipt(3,3,"b"*64)),
                         "requires_chain_verification")
    def test_malformed_receipt_denied(self):
        with self.assertRaises(AnchorContinuityDenied):
            verify_continuity(receipt(1,1),{"count":2})

if __name__=="__main__":
    unittest.main()
