from dataclasses import replace
from decimal import Decimal as D
import unittest
from alpha_lab.paper.risk import RiskAuthoriser, CostModel, Limits
from fixtures import NOW, proposal, quote


class RiskBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.risk=RiskAuthoriser(CostModel(fee_bps='0',slippage_bps='0',gap_buffer='0'))
        self.account=dict(mode='simulation',halted=False,enabled=True,currency='AUD',last_time=NOW,
                          last_equity='10000',cash='10000',day_start='10000',week_start='10000',peak_equity='10000',
                          limits={k:str(v) if isinstance(v,D) else v for k,v in Limits().__dict__.items()})
        self.q=quote(bid='100',ask='100',ask_size='1000')
        self.p=proposal(quantity='2.5',stop_price='90')

    def evaluate(self, *, p=None, q=None, positions=(), orders=()):
        return self.risk.evaluate(p or self.p,q or self.q,self.account,list(positions),list(orders),NOW,broker_connected=True)[0]

    def test_position_risk_exact_boundary_and_above(self):
        self.assertEqual(self.evaluate(),())
        self.assertIn('POSITION_LOSS_LIMIT',self.evaluate(p=replace(self.p,quantity='2.500000001')))
        self.assertEqual(self.evaluate(p=replace(self.p,quantity='2.499999999')),())

    def test_aggregate_risk_boundary_and_above(self):
        position=dict(instrument='OTHER/AUD',quantity='1',mark='100',planned_loss='75')
        self.assertEqual(self.evaluate(positions=[position]),())
        position['planned_loss']='75.000001'
        self.assertIn('AGGREGATE_STOP_RISK_LIMIT',self.evaluate(positions=[position]))

    def test_daily_loss_exact_boundary_and_just_below(self):
        self.account['last_equity']='9800'
        self.assertIn('DAILY_LOSS_SUSPENSION',self.evaluate())
        self.account['last_equity']='9800.000001'
        self.assertNotIn('DAILY_LOSS_SUSPENSION',self.evaluate())

    def test_drawdown_exact_boundary_and_just_below(self):
        self.account['last_equity']='9500'
        self.assertIn('DRAWDOWN_SUSPENSION',self.evaluate())
        self.account['last_equity']='9500.000001'
        self.assertNotIn('DRAWDOWN_SUSPENSION',self.evaluate())

    def test_weekly_loss_boundary(self):
        self.account['last_equity']='9600'
        self.assertIn('WEEKLY_LOSS_SUSPENSION',self.evaluate())

    def test_concentration_and_total_exposure(self):
        p=replace(self.p,quantity='21',stop_price='99.9')
        self.assertIn('CONCENTRATION_LIMIT',self.evaluate(p=p))
        existing=dict(instrument='OTHER/AUD',quantity='29',mark='100',planned_loss='1')
        self.assertIn('EXPOSURE_LIMIT',self.evaluate(positions=[existing]))

    def test_insufficient_cash_and_disabled_account(self):
        self.account['cash']='1'
        self.assertIn('INSUFFICIENT_BUYING_POWER',self.evaluate())
        self.account['enabled']=False
        self.assertIn('SIMULATION_SUSPENDED',self.evaluate())

    def test_maximum_order_frequency(self):
        orders=[dict(status='FILLED',created_at=NOW) for _ in range(10)]
        self.assertIn('ORDER_FREQUENCY_LIMIT',self.evaluate(orders=orders))

    def test_missing_or_stale_broker_state_never_approved(self):
        for connected in (False,None,'true',1):
            result=self.risk.evaluate(self.p,self.q,self.account,[],[],NOW,broker_connected=connected)
            self.assertIn('BROKER_DISCONNECTED',result[0])

    def test_loss_includes_entry_exit_fee_and_gap_buffer(self):
        model=CostModel(fee_bps='10',slippage_bps='5',gap_buffer='0.01')
        # 2*(100-98 + 0.98) + (2*198*0.001) = 6.356 AUD.
        self.assertEqual(model.planned_loss(D('2'),D('100'),D('98')),D('6.356'))

if __name__=='__main__': unittest.main()
