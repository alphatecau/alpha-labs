import unittest
from alpha_lab.research.causal_regimes import causal_regime_labels

class CausalRegimeTests(unittest.TestCase):
    def test_past_labels_unchanged_when_future_changes(self):
        history=[100+i*.1 for i in range(400)]
        first=causal_regime_labels(history)
        extended=causal_regime_labels(history+[1000]*50)
        self.assertEqual(first,extended[:400])

    def test_next_bar_cannot_change_current_label(self):
        history=[100+i*.1 for i in range(400)]
        original=causal_regime_labels(history)
        changed=history.copy()
        changed[-1]=99999
        updated=causal_regime_labels(changed)
        self.assertEqual(original[-1],updated[-1])

    def test_invalid_prices_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"Invalid prices"):
            causal_regime_labels([100.0]*200+[0.0])

    def test_short_history_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Insufficient history"):
            causal_regime_labels([100.0]*20)

if __name__=="__main__":
    unittest.main()
