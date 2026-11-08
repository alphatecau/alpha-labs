import unittest
from alpha_lab.research.phase1_benchmarks import risk_matched_buy_hold

class Phase1BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.prices={"BTCUSDT":[100+i*.1 for i in range(130)],
                     "ETHUSDT":[90+i*.2 for i in range(130)]}
    def test_no_future_leakage_in_sizing(self):
        a=risk_matched_buy_hold(self.prices,start=80,end=120)
        self.prices["BTCUSDT"][110]=999999
        b=risk_matched_buy_hold(self.prices,start=80,end=120)
        self.assertEqual(a["weights"],b["weights"])
        self.assertEqual(a["sizing_last_observation_index"],79)
    def test_cap_and_cost_sensitivity(self):
        a=risk_matched_buy_hold(self.prices,start=80,end=120,fee_bps=10,slippage_bps=10)
        b=risk_matched_buy_hold(self.prices,start=80,end=120,fee_bps=40,slippage_bps=40)
        self.assertLessEqual(sum(a["weights"].values()),1)
        self.assertTrue(all(w<=.15 for w in a["weights"].values()))
        self.assertGreater(a["return_pct"],b["return_pct"])
        self.assertFalse(a["live_trading"])
    def test_invalid_inputs_fail_closed(self):
        self.prices["BTCUSDT"][60]=0
        with self.assertRaises(ValueError):
            risk_matched_buy_hold(self.prices,start=80,end=120)

if __name__=="__main__":unittest.main()
