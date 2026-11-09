import unittest
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from alpha_lab.research.paper_market_provenance import MarketObservation,validate_observation

class MarketProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,9,tzinfo=timezone.utc)
    def obs(self,**overrides):
        values=dict(symbol="BTC",mid=Decimal("100"),timestamp=self.now,source="approved-test-feed")
        values.update(overrides)
        return MarketObservation(**values)
    def check_denied(self,observation,**kwargs):
        with self.assertRaisesRegex(ValueError,"HALT"):
            validate_observation(observation,now=self.now,allowed_sources=("approved-test-feed",),**kwargs)
    def test_approved_structure(self):
        self.assertEqual(validate_observation(self.obs(),now=self.now,allowed_sources=("approved-test-feed",)).mid,Decimal("100"))
    def test_unknown_source_denied(self):
        self.check_denied(self.obs(source="untrusted"))
    def test_missing_allowlist_denied(self):
        with self.assertRaisesRegex(ValueError,"HALT"):
            validate_observation(self.obs(),now=self.now)
    def test_stale_future_and_non_utc_denied(self):
        self.check_denied(self.obs(timestamp=self.now-timedelta(seconds=61)))
        self.check_denied(self.obs(timestamp=self.now+timedelta(seconds=1)))
        self.check_denied(self.obs(timestamp=self.now.replace(tzinfo=None)))
        self.check_denied(self.obs(timestamp=self.now.astimezone(timezone(timedelta(hours=10)))))
    def test_bad_prices_denied(self):
        for value in ("0","-1","NaN","Infinity"):
            self.check_denied(self.obs(mid=value))
if __name__=="__main__":
    unittest.main()
