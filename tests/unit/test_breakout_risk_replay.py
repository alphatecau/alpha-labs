import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from alpha_lab.data.csv_import import Bar
from alpha_lab.backtest.costs import CostModel
from alpha_lab.research.breakout_risk_replay import replay_breakout_risk
from alpha_lab.research.breakout_reconcile import reconcile_risk_replay

def bars_fixture(n=900, *, stop_hour=None, gap_hour=None):
    origin=datetime(2025,1,1,tzinfo=timezone.utc)
    result=[]
    for i in range(n):
        o=Decimal("100")+Decimal(i)/Decimal("100")
        low=o-Decimal("1")
        if i == stop_hour: low=o-Decimal("20")
        if i == gap_hour:
            o=o-Decimal("30")
            low=o-Decimal("1")
        result.append(Bar(origin+timedelta(hours=i),o,o+Decimal("1"),low,o,Decimal("10")))
    return tuple(result)

class RiskReplayTests(unittest.TestCase):
    def test_no_signal_has_no_orders_and_reconciles(self):
        bars=bars_fixture()
        costs=CostModel()
        report=replay_breakout_risk(bars,[False]*len(bars),840,900,costs=costs)
        self.assertEqual(report["executed_orders"],0)
        self.assertEqual(report["final_liquidatable_value"],"10000")
        self.assertEqual(reconcile_risk_replay(bars,840,900,report,costs)["status"],"PASS")

    def test_entry_risk_and_intrabar_stop(self):
        bars=bars_fixture(stop_hour=851)
        signals=[False]*len(bars)
        signals[843:]=[True]*(len(bars)-843)
        costs=CostModel()
        report=replay_breakout_risk(bars,signals,844,860,costs=costs)
        self.assertTrue(any(o["kind"]=="BUY" for o in report["orders"]))
        self.assertTrue(any(o["reason"]=="intrabar_stop_modelled" for o in report["orders"]))
        for order in report["orders"]:
            if order["kind"]=="BUY":
                self.assertLessEqual(Decimal(order["planned_loss_including_costs"]),Decimal("25.000000000001"))
                self.assertLessEqual(Decimal(order["quote_outlay"]),Decimal("2000.000000000001"))
        self.assertEqual(reconcile_risk_replay(bars,844,860,report,costs)["status"],"PASS")

    def test_gap_stop_does_not_fill_at_stale_stop(self):
        bars=bars_fixture(gap_hour=851)
        signals=[False]*len(bars)
        signals[843:]=[True]*(len(bars)-843)
        report=replay_breakout_risk(bars,signals,844,860)
        gaps=[o for o in report["orders"] if o["reason"]=="gap_stop"]
        self.assertTrue(gaps)
        self.assertLess(Decimal(gaps[0]["price"]),Decimal("90"))
        self.assertEqual(reconcile_risk_replay(bars,844,860,report,CostModel())["status"],"PASS")

    def test_tampered_nav_fails_reconciliation(self):
        bars=bars_fixture()
        report=replay_breakout_risk(bars,[False]*len(bars),840,900)
        report["nav_curve"][0]="10001"
        with self.assertRaisesRegex(ValueError,"NAV reconciliation failed"):
            reconcile_risk_replay(bars,840,900,report,CostModel())

    def test_missing_hour_fails_closed(self):
        bars=bars_fixture()
        with self.assertRaisesRegex(ValueError,"Missing hourly candle"):
            replay_breakout_risk(bars[:300]+bars[301:],[False]*(len(bars)-1),840,899)

if __name__=="__main__":
    unittest.main()
