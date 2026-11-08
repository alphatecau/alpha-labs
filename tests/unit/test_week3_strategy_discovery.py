import unittest
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from alpha_lab.data.csv_import import Bar
from alpha_lab.research.week3_signals import single_market_proposals,proposals
from alpha_lab.research.week3_portfolio import simulate

class Week3Tests(unittest.TestCase):
    def setUp(self):
        self.prices=[100+i*.01 for i in range(920)]
        self.bars={}
        for s in ("BTCUSDT","ETHUSDT","SOLUSDT"):
            self.bars[s]=tuple(Bar(datetime(2023,1,1,tzinfo=timezone.utc)+timedelta(hours=i),
                Decimal(str(p)),Decimal(str(p+1)),Decimal(str(p-1)),Decimal(str(p)),Decimal("100"))
                for i,p in enumerate(self.prices))

    def test_lagged_signals_do_not_respond_to_current_price(self):
        original=single_market_proposals(self.prices,"H1")
        modified=self.prices.copy()
        modified[-1]=100000
        self.assertEqual(original[-1],single_market_proposals(modified,"H1")[-1])
        original2=single_market_proposals(self.prices,"H2")
        self.assertEqual(original2[-1],single_market_proposals(modified,"H2")[-1])

    def test_rotation_causal_and_deterministic(self):
        x={s:self.prices.copy() for s in self.bars}
        first=proposals(x,"H3")
        for s in x:x[s][-1]=1
        self.assertEqual(first[-1],proposals(x,"H3")[-1])

    def test_cash_only_accounting_and_no_trading(self):
        r=simulate(self.bars,[None]*920,840,920,10)
        self.assertEqual(r["return_pct"],0)
        self.assertEqual(r["cash_ledger_reconciliation"],"PASS")
        self.assertFalse(r["live_trading"])
        self.assertFalse(r["risk_authority_independent"])

    def test_invalid_target_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Invalid target"):
            simulate(self.bars,["BAD"]*920,840,920,10)

if __name__=="__main__":
    unittest.main()
