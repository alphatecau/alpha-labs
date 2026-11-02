import csv
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from alpha_lab.data.csv_import import load_csv
from alpha_lab.backtest.costs import CostModel
from alpha_lab.backtest.engine import replay
from alpha_lab.research.strategies.momentum import ema_signal
from alpha_lab.research.metrics import evaluate

class ResearchFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'data.csv'
        self.rows=[]
        for i in range(130):
            price=Decimal(100+i)/Decimal(1)
            t=(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(hours=i)).isoformat()
            self.rows.append([t,str(price),str(price+1),str(price-1),str(price),'100'])
        self.write()
    def write(self):
        with self.path.open('w',newline='') as f:
            wr=csv.writer(f);wr.writerow(['timestamp','open','high','low','close','volume']);wr.writerows(self.rows)
    def ds(self):return load_csv(self.path,quote_currency='USDC',provenance='synthetic-test')
    def test_valid_dataset(self):
        d=self.ds();self.assertEqual(len(d.bars),130);self.assertEqual(d.quote_currency,'USDC');self.assertEqual(len(d.sha256),64)
    def test_duplicate_timestamp_rejected(self):
        self.rows[18][0]=self.rows[17][0];self.write()
        with self.assertRaisesRegex(ValueError,'duplicate'):self.ds()
    def test_gap_rejected(self):
        self.rows.pop(17);self.write()
        with self.assertRaisesRegex(ValueError,'irregular'):self.ds()
    def test_negative_price_rejected(self):
        self.rows[20][4]='-2';self.write()
        with self.assertRaises(ValueError):self.ds()
    def test_naive_timestamp_rejected(self):
        self.rows[0][0]='2026-01-01T00:00:00';self.write()
        with self.assertRaisesRegex(ValueError,'timezone'):self.ds()
    def test_currency_explicit(self):
        with self.assertRaises(ValueError):load_csv(self.path,quote_currency='SOL')
    def test_cost_model_is_adverse(self):
        c=CostModel(Decimal('10'),Decimal('20'))
        qty=c.buy_quantity(Decimal('200'),Decimal('100'))
        self.assertAlmostEqual(float(c.buy_outlay(qty,Decimal('100'))),200)
        self.assertLess(c.sell_proceeds(qty,Decimal('100')),Decimal('200'))
    def test_signal_is_past_only(self):
        a=[b.close for b in self.ds().bars]
        short=ema_signal(a[:100]);long=ema_signal(a[:100]+[Decimal('999999')]*30)
        self.assertEqual(short,long[:100])
    def test_no_same_candle_entry(self):
        bars=self.ds().bars
        flags=[False]*len(bars);flags[50]=True
        r=replay(bars,flags,50,54)
        self.assertEqual(r.orders[0]['time'],bars[51].time.isoformat())
    def test_allocation_ceiling(self):
        bars=self.ds().bars
        r=replay(bars,[True]*len(bars),60,61,max_allocation=Decimal('0.1'))
        self.assertLessEqual(Decimal(r.orders[0]['quote_outlay']),Decimal('1000.0000001'))
    def test_larger_cost_reduces_constant_price_nav(self):
        bars=self.ds().bars
        # On this rising price example two models should still respect more costly buy-and-sell.
        r1=replay(bars,[True]*len(bars),60,70,costs=CostModel(Decimal('10'),Decimal('10')))
        r2=replay(bars,[True]*len(bars),60,70,costs=CostModel(Decimal('20'),Decimal('20')))
        self.assertGreater(Decimal(r1.final_liquidatable_value),Decimal(r2.final_liquidatable_value))
    def test_replay_is_deterministic(self):
        d=self.ds();sig=ema_signal([b.close for b in d.bars]);a=replay(d.bars,sig,60,100);b=replay(d.bars,sig,60,100)
        self.assertEqual(a,b)
    def test_split_and_provenance(self):
        r=evaluate(self.ds())
        self.assertEqual(r['dataset']['split_index'],91)
        self.assertEqual(r['dataset']['provenance'],'synthetic-test')
        self.assertEqual(set(r['periods']),{'training','holdout'})
        self.assertIn('NOT_VALIDATED_ALPHA',r['status'])
    def test_position_mark_is_cost_adjusted(self):
        d=self.ds();r=evaluate(d)
        self.assertIn('final_liquidatable_value',r['periods']['holdout']['strategy'])
    def test_reject_invalid_allocation(self):
        d=self.ds()
        with self.assertRaises(ValueError):replay(d.bars,[True]*len(d.bars),60,70,max_allocation=Decimal('1.1'))
if __name__=='__main__':unittest.main()
