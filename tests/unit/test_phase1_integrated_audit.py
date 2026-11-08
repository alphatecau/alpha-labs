import unittest
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from unittest.mock import patch
from alpha_lab.data.csv_import import Bar
from alpha_lab.research.week3_portfolio import simulate
from alpha_lab.research.phase1_accounting import reconcile_simulation

class IntegratedAuditTests(unittest.TestCase):
    def setUp(self):
        self.bars={}
        for s in ("BTCUSDT","ETHUSDT","SOLUSDT"):
            self.bars[s]=tuple(
                Bar(datetime(2024,1,1,tzinfo=timezone.utc)+timedelta(hours=i),
                    Decimal("100"),Decimal("101"),Decimal("99"),Decimal("100"),Decimal("1000"))
                for i in range(880))

    def test_flat_portfolio_reconciles_every_fold(self):
        r=simulate(self.bars,[None]*880,840,880,20)
        self.assertEqual(r["independent_position_nav_reconciliation"],"PASS")
        self.assertEqual(r["independent_audit_order_count"],0)

    def test_live_position_reconciles_at_final_bar(self):
        target=[None]*880
        for i in range(840,880):target[i]="BTCUSDT"
        r=simulate(self.bars,target,840,880,20)
        self.assertEqual(r["independent_position_nav_reconciliation"],"PASS")
        self.assertGreater(r["independent_audit_order_count"],0)
        self.assertFalse(r["promotion_authorised"])

    def test_auditor_failure_blocks_result(self):
        with patch("alpha_lab.research.week3_portfolio.reconcile_simulation",side_effect=ValueError("NAV mismatch")):
            with self.assertRaisesRegex(ValueError,"NAV mismatch"):
                simulate(self.bars,[None]*880,840,880,20)

    def test_tampered_final_nav_rejected(self):
        r={"orders":[],"final_cash":"10000","final_nav":"10001","total_fees":"0"}
        with self.assertRaisesRegex(ValueError,"NAV mismatch"):
            reconcile_simulation(r,{"BTCUSDT":Decimal("100")},liquidation_bps=Decimal("0"))

if __name__=="__main__":unittest.main()
