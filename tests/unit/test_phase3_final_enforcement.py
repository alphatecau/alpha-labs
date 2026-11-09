import unittest
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from alpha_lab.backtest.engine import replay
from alpha_lab.backtest.costs import CostModel
from alpha_lab.data.csv_import import Bar
from alpha_lab.research.phase3_integrity import Session,reconstruct_replay_economics

UTC=timezone.utc
class FinalEnforcementTests(unittest.TestCase):
    def bars(self):
        origin=datetime(2026,4,2,13,30,tzinfo=UTC)
        return tuple(Bar(origin+timedelta(hours=i),Decimal('100'),Decimal('101'),Decimal('99'),Decimal('100'),Decimal('1')) for i in range(12))
    def test_equity_rejects_missing_calendar(self):
        with self.assertRaisesRegex(ValueError,'sessions'):
            replay(self.bars(),[True]*12,1,5,venue='equity')
    def test_fabricated_closed_session_candle_rejected(self):
        b=self.bars()
        sessions=[Session(b[0].time,b[1].time)]
        with self.assertRaisesRegex(ValueError,'outside verified'):
            replay(b,[True]*12,1,5,venue='equity',sessions=sessions)
    def test_valid_equity_session_and_reconstructed_nav(self):
        b=self.bars()
        sessions=[Session(b[0].time,b[6].time)]
        result=replay(b,[True]*12,1,5,venue='equity',sessions=sessions)
        self.assertTrue(result.open_position)
        reconstructed=reconstruct_replay_economics(b,result.orders,result.starting_balance,CostModel(),result.final_liquidatable_value,last_close=b[4].close)
        self.assertEqual(reconstructed['nav'],Decimal(result.final_liquidatable_value))
    def test_tampered_fee_and_price_rejected(self):
        b=self.bars()
        result=replay(b,[True]*12,1,5)
        for key in ('fee','price','quote_outlay'):
            orders=[dict(o) for o in result.orders]
            orders[0][key]=str(Decimal(orders[0][key])+Decimal('1'))
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'mismatch'):
                reconstruct_replay_economics(b,orders,result.starting_balance,CostModel(),result.final_liquidatable_value,last_close=b[4].close)
    def test_tampered_open_position_nav_rejected(self):
        b=self.bars()
        result=replay(b,[True]*12,1,5)
        with self.assertRaisesRegex(ValueError,'NAV mismatch'):
            reconstruct_replay_economics(b,result.orders,result.starting_balance,CostModel(),Decimal(result.final_liquidatable_value)+1,last_close=b[4].close)
if __name__=='__main__':unittest.main()
