import unittest
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from alpha_lab.data.csv_import import Bar
from alpha_lab.research.phase1_accounting import reconstruct,reconcile_simulation
from alpha_lab.research.phase1_evidence import (
    canonical_hash,experiment_record,verify_registry,verify_hourly_utc_grid,
    verify_signal_availability,execution_cost_bridge,lagged_volatility_weights)

class Phase1EvidenceTests(unittest.TestCase):
    def test_independent_order_and_nav_reconstruction(self):
        orders=[dict(side="BUY",symbol="BTCUSDT",quantity="2",price="100",fee="1",cash_delta="-201"),
                dict(side="SELL",symbol="BTCUSDT",quantity="1",price="110",fee="1",cash_delta="109")]
        r=reconstruct(orders,{"BTCUSDT":"120"},liquidation_bps="0")
        self.assertEqual(r["cash"],"9908")
        self.assertEqual(r["positions"]["BTCUSDT"],"1")
        self.assertEqual(r["final_liquidation_nav"],"10028")
        self.assertEqual(r["fees"],"2")
        self.assertTrue(r["reconciled"])

    def test_tampered_delta_rejected(self):
        with self.assertRaisesRegex(ValueError,"cash delta"):
            reconstruct([dict(side="BUY",symbol="BTCUSDT",quantity="1",price="100",fee="1",cash_delta="-100")],
                        {"BTCUSDT":"100"})

    def test_naked_short_rejected(self):
        with self.assertRaisesRegex(ValueError,"Naked"):
            reconstruct([dict(side="SELL",symbol="BTCUSDT",quantity="1",price="100",fee="0",cash_delta="100")],
                        {"BTCUSDT":"100"})

    def test_false_nav_rejected(self):
        s={"orders":[],"final_cash":"10000","final_nav":"11000","total_fees":"0"}
        with self.assertRaisesRegex(ValueError,"NAV mismatch"):
            reconcile_simulation(s,{"BTCUSDT":"100"},liquidation_bps="0")

    def test_nonfinite_and_negative_fee_rejected(self):
        for fee in ("NaN","-1"):
            with self.assertRaises(ValueError):
                reconstruct([dict(side="BUY",symbol="BTCUSDT",quantity="1",price="100",fee=fee,cash_delta="-100")],
                            {"BTCUSDT":"100"})

    def test_registry_tamper_and_duplicate(self):
        r=experiment_record("P1-DIV-TREND-001","a"*64,"f"*40,{"BTCUSDT":"b"*64})
        self.assertTrue(verify_registry([r]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            verify_registry([r,r])
        r["record"]["status"]="FAIL"
        with self.assertRaisesRegex(ValueError,"Tampered"):
            verify_registry([r])

    def test_causal_time(self):
        t=datetime(2026,1,1,tzinfo=timezone.utc)
        self.assertTrue(verify_signal_availability(t,t+timedelta(hours=1)))
        with self.assertRaisesRegex(ValueError,"Lookahead"):
            verify_signal_availability(t,t)

    def test_duplicate_missing_grid(self):
        t=datetime(2026,1,1,tzinfo=timezone.utc)
        def bar(hour):
            return Bar(t+timedelta(hours=hour),Decimal("100"),Decimal("101"),Decimal("99"),Decimal("100"),Decimal("1"))
        self.assertTrue(verify_hourly_utc_grid([bar(0),bar(1)]))
        for rows in ([bar(0),bar(0)],[bar(0),bar(2)],[bar(1),bar(0)]):
            with self.assertRaises(ValueError):verify_hourly_utc_grid(rows)

    def test_cost_bridge(self):
        r=execution_cost_bridge([dict(side="BUY",quantity="2",reference_mid="100",executed_price="101",fee="1")])
        self.assertEqual(r["combined_cost"],"3")
        self.assertFalse(r["spread_vs_impact_separately_identifiable"])

    def test_lagged_benchmark_no_current_close_leakage(self):
        prices={"BTCUSDT":[100+i*.1 for i in range(70)],"ETHUSDT":[90+i*.2 for i in range(70)]}
        first=lagged_volatility_weights(prices)
        prices["BTCUSDT"][-1]=100000
        self.assertEqual(first,lagged_volatility_weights(prices))

if __name__=="__main__":unittest.main()
