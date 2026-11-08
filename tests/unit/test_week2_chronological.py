import unittest
from alpha_lab.research.selection_gate import exact_two_sided_sign_test,selection_aware_gate
from scripts.week2_chronological_replay import partitions

class Week2ChronologicalTests(unittest.TestCase):
    def test_embargoed_folds_are_ordered_disjoint(self):
        windows=partitions(24000)
        self.assertEqual(len(windows),5)
        self.assertTrue(all(b>a>=888 for a,b in windows))
        self.assertTrue(all(windows[i][1]<windows[i+1][0] for i in range(4)))

    def test_five_positive_folds_cannot_pass_nine_comparisons(self):
        self.assertEqual(exact_two_sided_sign_test(5,0),.0625)
        fake=[{"market":a,"cost_bps_fee_and_slippage_each_side":c,
               "folds":[{"return_pct":1.0}]*5}
              for a in ("BTCUSDT","ETHUSDT","SOLUSDT") for c in (10,20,40)]
        decision=selection_aware_gate(fake)
        self.assertEqual(decision["statistical_validation"],"NOT_ESTABLISHED")
        self.assertTrue(all(not x["statistically_significant"] for x in decision["comparisons"]))

    def test_insufficient_history_rejected(self):
        with self.assertRaisesRegex(ValueError,"Insufficient"):
            partitions(1000)

if __name__=="__main__":
    unittest.main()
