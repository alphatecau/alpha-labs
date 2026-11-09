import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from alpha_lab.research.paper_simulator import PaperLedger
from alpha_lab.research.paper_market_provenance import MarketObservation
from alpha_lab.research.paper_verified_valuation import derive_verified_portfolio

class VerifiedValuationTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,9,tzinfo=timezone.utc)
        self.ledger=PaperLedger("1000")
        self.ledger.enable_simulation(operator_approved=True)
        self.ledger.fill(symbol="BTC",side="BUY",quantity="1",reference_mid="100",executed_price="100",fee="1")
    def obs(self,**kwargs):
        fields=dict(symbol="BTC",mid=Decimal("110"),timestamp=self.now,source="fixture")
        fields.update(kwargs)
        return MarketObservation(**fields)
    def test_derived_valuation_from_validated_observation(self):
        result=derive_verified_portfolio(self.ledger,{"BTC":self.obs()},now=self.now,allowed_sources=("fixture",))
        self.assertEqual(result.nav,Decimal("1009"))
        self.assertEqual(result.gross_notional,Decimal("110"))
    def test_untrusted_or_stale_quotes_rejected(self):
        for obs in (self.obs(source="forged"),self.obs(timestamp=self.now-timedelta(minutes=2)),self.obs(symbol="ETH")):
            with self.assertRaisesRegex(ValueError,"HALT"):
                derive_verified_portfolio(self.ledger,{"BTC":obs},now=self.now,allowed_sources=("fixture",))
    def test_missing_observation_denied(self):
        with self.assertRaisesRegex(ValueError,"HALT"):
            derive_verified_portfolio(self.ledger,{},now=self.now,allowed_sources=("fixture",))
if __name__=="__main__":
    unittest.main()
