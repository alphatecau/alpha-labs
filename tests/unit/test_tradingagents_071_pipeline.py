import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from alpha_lab.data.csv_import import Bar
from alpha_lab.backtest.engine import replay
from alpha_lab.backtest.costs import CostModel
from alpha_lab.research.point_in_time_guards import register_run_id

class PipelineIntegrationTests(unittest.TestCase):
    def bars(self):
        origin=datetime(2026,1,1,tzinfo=timezone.utc)
        # Synthetic exchange closure: 72-hour gap; no signal may be settled inside the gap.
        times=[origin+timedelta(hours=i) for i in range(90)]
        times=[t if i<40 else t+timedelta(hours=72) for i,t in enumerate(times)]
        return tuple(Bar(t,Decimal('100'),Decimal('101'),Decimal('99'),Decimal('100'),Decimal('1')) for t in times)

    def test_holiday_gap_next_available_bar_settlement(self):
        bars=self.bars()
        signals=[False]*len(bars)
        signals[39]=True
        result=replay(bars,signals,39,43)
        self.assertEqual(result.orders[0]['time'],bars[40].time.isoformat())
        self.assertEqual(result.orders[0]['kind'],'BUY')

    def test_nonfinite_costs_rejected(self):
        for v in ('NaN','Infinity','-Infinity'):
            with self.subTest(value=v), self.assertRaises(ValueError):
                CostModel(Decimal(v),Decimal('10'))

    def test_nonfinite_replay_cash_rejected(self):
        with self.assertRaises(ValueError):
            replay(self.bars(),[False]*90,10,20,starting_balance=Decimal('NaN'))

    def test_duplicate_run_id_rejected(self):
        registry={}
        evidence='a'*64
        register_run_id(registry,'run-1',evidence)
        with self.assertRaisesRegex(ValueError,'duplicate'):
            register_run_id(registry,'run-1',evidence)
        self.assertEqual(registry,{'run-1':evidence})

    def test_invalid_run_evidence_rejected(self):
        with self.assertRaises(ValueError):
            register_run_id({},'run-2','not-a-sha')

if __name__=='__main__':
    unittest.main()
